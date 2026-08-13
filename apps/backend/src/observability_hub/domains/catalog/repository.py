"""Queries do domínio catalog. Única camada que constrói SQL e interpreta
linhas cruas do INFORMATION_SCHEMA — service.py nunca vê SQL nem objetos do
client do BigQuery além do que essas funções retornam.
"""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from google.cloud import bigquery

# resolve_dataset_region é re-exportado para manter repository.resolve_dataset_region
# (usado por service.py e pelos testes existentes) — implementação mora em
# core/bigquery porque é compartilhada entre domínios (ver core/exceptions.py).
from observability_hub.core.bigquery import (
    get_table_cached,
    get_tables_metadata,
    resolve_dataset_region,  # noqa: F401
)
from observability_hub.core.exceptions import TableNotFoundError

# INFORMATION_SCHEMA.TABLES usa "BASE TABLE" e "MATERIALIZED VIEW" (com
# espaço); a API expõe os valores documentados na spec (catalog.md v1.2).
_RAW_TABLE_TYPE_TO_API = {
    "BASE TABLE": "TABLE",
    "VIEW": "VIEW",
    "EXTERNAL": "EXTERNAL",
    "MATERIALIZED VIEW": "MATERIALIZED_VIEW",
}
_API_TABLE_TYPE_TO_RAW = {v: k for k, v in _RAW_TABLE_TYPE_TO_API.items()}

# get_partition_stats roda uma query real (custo != $0, ver função) — cacheada
# por tabela pra não repetir a cada refresh de tela.
_PARTITION_STATS_CACHE_TTL_SECONDS = 300
_partition_stats_cache: dict[str, tuple[float, dict]] = {}
_partition_stats_cache_lock = threading.Lock()

# Usado por derive_search_prefix — tabelas com sufixo numérico (ex:
# events_20260812, sharded/particionadas por nome) tratadas como uma série;
# o prefixo sem o sufixo identifica a série (events_).
_TRAILING_DIGITS_RE = re.compile(r"\d+$")


def _bytes_to_gb(size_bytes: int | None) -> float | None:
    if size_bytes is None:
        return None
    return round(size_bytes / 1_000_000_000, 4)


def get_datasets_summary(
    client: bigquery.Client, project_id: str, regions: list[str]
) -> list[dict]:
    """Query 2 da spec, rodada uma vez por região — INFORMATION_SCHEMA.SCHEMATA
    é region-qualified, não dá pra combinar regiões numa única query."""
    datasets: list[dict] = []
    for region in regions:
        query = f"""
            SELECT
              s.schema_name                                          AS dataset_id,
              s.location,
              s.creation_time,
              s.last_modified_time,
              COUNTIF(t.table_type = 'BASE TABLE')                   AS total_tables,
              COUNTIF(t.table_type IN ('VIEW','MATERIALIZED VIEW'))  AS total_views,
              COALESCE(SUM(ts.total_logical_bytes), 0)               AS total_size_bytes,
              COALESCE(SUM(ts.total_rows), 0)                        AS total_rows
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.SCHEMATA` s
            LEFT JOIN `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLES` t
              ON t.table_schema = s.schema_name
            LEFT JOIN `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLE_STORAGE` ts
              ON ts.table_schema = t.table_schema
             AND ts.table_name   = t.table_name
            GROUP BY 1, 2, 3, 4
            ORDER BY total_size_bytes DESC
        """
        rows = client.query(query).result()
        for row in rows:
            datasets.append(
                {
                    "dataset_id": row.dataset_id,
                    "location": row.location,
                    "creation_time": row.creation_time,
                    "last_modified_time": row.last_modified_time,
                    "total_tables": row.total_tables,
                    "total_views": row.total_views,
                    "total_size_bytes": row.total_size_bytes,
                    "total_size_gb": _bytes_to_gb(row.total_size_bytes) or 0.0,
                    "total_rows": row.total_rows,
                }
            )
    return datasets


def derive_search_prefix(query: str) -> str | None:
    """Remove o sufixo numérico final de query (ex: "events_20260812" ->
    "events_"). None se query não termina em dígito — sem sufixo numérico
    não há uma "série" de tabelas pra comparar (usado pela busca reversa
    pra explicar datasets sem a tabela buscada, ver search_tables_by_prefix)."""
    match = _TRAILING_DIGITS_RE.search(query)
    if match is None:
        return None
    prefix = query[: match.start()]
    return prefix or None


def search_tables(
    client: bigquery.Client,
    project_id: str,
    regions: list[str],
    query: str,
    mode: str,
    max_workers: int = 8,
) -> list[dict]:
    """Busca table_name = query (mode="exact") ou table_name LIKE '%query%'
    (mode="contains") em INFORMATION_SCHEMA.TABLES de todas as regiões do
    projeto, uma query por região em paralelo (mesma técnica de
    core.bigquery.discover_regions)."""
    if not regions:
        return []

    def _search_region(region: str) -> list[dict]:
        if mode == "exact":
            where = "table_name = @q"
            params = [bigquery.ScalarQueryParameter("q", "STRING", query)]
        else:
            where = "table_name LIKE @q"
            params = [bigquery.ScalarQueryParameter("q", "STRING", f"%{query}%")]
        sql = f"""
            SELECT table_schema AS dataset_id, table_name AS table_id, table_type
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLES`
            WHERE {where}
        """
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = client.query(sql, job_config=job_config).result()
        return [
            {
                "dataset_id": row.dataset_id,
                "table_id": row.table_id,
                "table_type": _RAW_TABLE_TYPE_TO_API.get(row.table_type, row.table_type),
            }
            for row in rows
        ]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_search_region, regions))
    matches = [row for region_rows in results for row in region_rows]
    matches.sort(key=lambda m: (m["dataset_id"], m["table_id"]))
    return matches


def search_tables_by_prefix(
    client: bigquery.Client,
    project_id: str,
    regions: list[str],
    prefix: str,
    exclude_dataset_ids: set[str],
    max_workers: int = 8,
) -> list[dict]:
    """Pra cada dataset com pelo menos uma tabela começando com prefix,
    retorna a última (MAX table_name) — usado pra explicar datasets sem a
    tabela exata buscada mas que têm a mesma série (ex: events_20260810 num
    dataset que não tem events_20260812 ainda). Datasets em
    exclude_dataset_ids (os que já bateram no match exato) são omitidos."""
    if not regions:
        return []

    def _search_region(region: str) -> list[dict]:
        sql = f"""
            SELECT table_schema AS dataset_id, MAX(table_name) AS latest_table
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLES`
            WHERE table_name LIKE @prefix
            GROUP BY 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("prefix", "STRING", f"{prefix}%")]
        )
        rows = client.query(sql, job_config=job_config).result()
        return [{"dataset_id": row.dataset_id, "latest_table": row.latest_table} for row in rows]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_search_region, regions))
    rows = [row for region_rows in results for row in region_rows]
    rows = [row for row in rows if row["dataset_id"] not in exclude_dataset_ids]
    rows.sort(key=lambda r: r["dataset_id"])
    return rows


def _partition_type_label(
    partition_column: str | None, bq_table: bigquery.Table | None
) -> str | None:
    """Formata como "{coluna} ({TIPO})", ex: "event_date (DAY)" — TIPO vem de
    table.time_partitioning.type_ (DAY/HOUR/MONTH/YEAR ou particionamento por
    ingestão, _PARTITIONTIME/_PARTITIONDATE) ou "RANGE" para
    table.range_partitioning. None se a tabela não é particionada ou se
    bq_table não foi resolvido (race, ver _row_to_table_dict)."""
    if partition_column is None or bq_table is None:
        return None
    if bq_table.time_partitioning is not None and bq_table.time_partitioning.type_:
        return f"{partition_column} ({bq_table.time_partitioning.type_})"
    if bq_table.range_partitioning is not None:
        return f"{partition_column} (RANGE)"
    return partition_column


def _row_to_table_dict(row, location: str, bq_table: bigquery.Table | None) -> dict:
    """bq_table vem de client.get_table() (core.bigquery.get_tables_metadata) —
    num_rows/num_bytes/modified em tempo real, sem o lag de até 24h de
    TABLE_STORAGE. None quando a tabela sumiu entre a query de listagem e a
    chamada da API (race) ou quando client.get_table() não retorna o campo
    (ex: VIEW não tem num_rows/num_bytes)."""
    clustering_columns = list(row.clustering_columns or [])
    partition_column = row.partition_column
    size_bytes = bq_table.num_bytes if bq_table is not None else None
    return {
        "table_id": row.table_name,
        "table_type": _RAW_TABLE_TYPE_TO_API.get(row.table_type, row.table_type),
        "creation_time": row.creation_time,
        "last_modified_time": bq_table.modified if bq_table is not None else None,
        "size_bytes": size_bytes,
        "size_gb": _bytes_to_gb(size_bytes),
        "row_count": bq_table.num_rows if bq_table is not None else None,
        "column_count": row.column_count,
        "is_partitioned": partition_column is not None,
        "partition_column": partition_column,
        "partition_type": _partition_type_label(partition_column, bq_table),
        "is_clustered": len(clustering_columns) > 0,
        "clustering_columns": clustering_columns,
        "location": location,
    }


def get_tables_summary(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    location: str,
    table_type: str | None = None,
) -> list[dict]:
    """Query 3 da spec, estendida para derivar is_clustered/clustering_columns
    e partition_column de INFORMATION_SCHEMA.COLUMNS (clustering_ordinal_position
    e is_partitioning_column) — a query documentada não fazia isso, mas o
    response da spec exige esses campos (divergência resolvida conforme
    combinado).

    INFORMATION_SCHEMA.TABLE_PARTITIONS não tem uma coluna com o nome da
    coluna de particionamento (só partition_id, o valor da partição) e não
    está disponível nas multi-regiões US/EU; TABLE_OPTIONS também não serve
    (só expõe pares chave/valor como require_partition_filter, sem o nome da
    coluna). COLUMNS.is_partitioning_column resolve isso de forma confiável
    em qualquer região, e a tabela já estava sendo consultada para as
    colunas de clustering.

    num_rows/size_bytes/last_modified_time vêm de client.get_table() (uma
    chamada por tabela, em paralelo, cacheada 5min em core.bigquery) em vez
    de INFORMATION_SCHEMA.TABLE_STORAGE — TABLE_STORAGE tem lag de até 24h
    após criação/atualização das tabelas, client.get_table() é tempo real.
    Como size_bytes não vem mais do SQL, o ORDER BY size_bytes DESC NULLS
    LAST da spec é replicado em Python depois do merge."""
    query_params = [bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id)]
    where_extra = ""
    if table_type is not None:
        raw_type = _API_TABLE_TYPE_TO_RAW.get(table_type, table_type)
        where_extra = " AND t.table_type = @table_type"
        query_params.append(bigquery.ScalarQueryParameter("table_type", "STRING", raw_type))

    query = f"""
        WITH columns_agg AS (
          SELECT
            table_schema,
            table_name,
            COUNT(column_name)                                       AS column_count,
            MAX(
              CASE WHEN is_partitioning_column = 'YES' THEN column_name END
            )                                                        AS partition_column,
            ARRAY_AGG(
              CASE WHEN clustering_ordinal_position IS NOT NULL THEN column_name END
              IGNORE NULLS
              ORDER BY clustering_ordinal_position
            )                                                        AS clustering_columns
          FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.COLUMNS`
          WHERE table_schema = @dataset_id
          GROUP BY 1, 2
        )
        SELECT
          t.table_name,
          t.table_type,
          t.creation_time,
          ANY_VALUE(COALESCE(ca.column_count, 0))           AS column_count,
          ANY_VALUE(ca.partition_column)                    AS partition_column,
          ANY_VALUE(COALESCE(ca.clustering_columns, []))    AS clustering_columns
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLES` t
        LEFT JOIN columns_agg ca
          ON ca.table_name = t.table_name AND ca.table_schema = t.table_schema
        WHERE t.table_schema = @dataset_id{where_extra}
        GROUP BY 1, 2, 3
    """
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    rows = list(client.query(query, job_config=job_config).result())

    table_refs = [f"{project_id}.{dataset_id}.{row.table_name}" for row in rows]
    metadata_by_ref = get_tables_metadata(client, table_refs)

    tables = [
        _row_to_table_dict(
            row, location, metadata_by_ref.get(f"{project_id}.{dataset_id}.{row.table_name}")
        )
        for row in rows
    ]
    tables.sort(key=lambda t: (t["size_bytes"] is None, -(t["size_bytes"] or 0)))
    return tables


def get_partition_stats(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    partition_field: str,
) -> dict:
    """Min/max/contagem (DISTINCT) real da coluna de partição — ao contrário
    de INFORMATION_SCHEMA (metadado gratuito), esta é uma query de dados de
    verdade e tem custo: INFORMATION_SCHEMA.PARTITIONS não existe em
    datasets multi-região (US/EU) e por isso não serve como fonte única.
    Custo é limitado por ler só a coluna de partição, sem filtro — mesmo
    assim, cacheado 5min por tabela (não por instância do Hub) pra não
    repetir a cada refresh de tela."""
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    now = time.monotonic()
    with _partition_stats_cache_lock:
        cached = _partition_stats_cache.get(table_ref)
    if cached is not None and now - cached[0] < _PARTITION_STATS_CACHE_TTL_SECONDS:
        return cached[1]

    query = f"""
        SELECT
          MIN(`{partition_field}`)            AS min_partition,
          MAX(`{partition_field}`)            AS max_partition,
          COUNT(DISTINCT `{partition_field}`) AS partition_count
        FROM `{table_ref}`
    """
    row = next(iter(client.query(query).result()))
    result = {
        "min_partition": None if row.min_partition is None else str(row.min_partition),
        "max_partition": None if row.max_partition is None else str(row.max_partition),
        "partition_count": row.partition_count,
    }
    with _partition_stats_cache_lock:
        _partition_stats_cache[table_ref] = (now, result)
    return result


def get_table_partitions(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    partition_field: str,
) -> list[dict]:
    """Lista as partições distintas de uma tabela particionada com a
    contagem de linhas de cada uma — query real de dados (não metadado),
    ordenada da mais recente pra mais antiga. GROUP BY já garante um valor
    distinto por linha, sem precisar de DISTINCT."""
    query = f"""
        SELECT `{partition_field}` AS partition_value, COUNT(*) AS row_count
        FROM `{project_id}.{dataset_id}.{table_id}`
        GROUP BY 1
        ORDER BY 1 DESC
    """
    rows = client.query(query).result()
    return [
        {"value": str(row.partition_value), "row_count": row.row_count}
        for row in rows
        if row.partition_value is not None
    ]


def get_table_columns(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    location: str,
) -> list[dict]:
    query = f"""
        SELECT c.column_name, c.data_type, c.is_nullable, cfp.description
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.COLUMNS` c
        LEFT JOIN `{project_id}.region-{location}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` cfp
          ON cfp.table_schema = c.table_schema
         AND cfp.table_name = c.table_name
         AND cfp.field_path = c.column_name
        WHERE c.table_schema = @dataset_id AND c.table_name = @table_id
        ORDER BY c.ordinal_position
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("table_id", "STRING", table_id),
        ]
    )
    rows = client.query(query, job_config=job_config).result()
    return [
        {
            "column_name": row.column_name,
            "data_type": row.data_type,
            # INFORMATION_SCHEMA.COLUMNS.is_nullable é STRING "YES"/"NO".
            "is_nullable": row.is_nullable == "YES",
            "description": row.description,
        }
        for row in rows
    ]


def get_table_detail(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    location: str,
) -> dict:
    """Reaproveita get_tables_summary para os metadados básicos e adiciona
    colunas completas + labels/description. labels/description vêm de
    client.get_table() (API tipada do BigQuery) em vez de parsear o literal
    SQL bruto de INFORMATION_SCHEMA.TABLE_OPTIONS — mesma fonte de dado
    (metadados, custo $0), leitura muito mais confiável. Usa o mesmo cache
    TTL de get_tables_summary (core.bigquery.get_table_cached) — como
    get_tables_summary acabou de rodar para a mesma tabela, esta chamada é
    um cache hit, sem round-trip extra à API."""
    tables = get_tables_summary(client, project_id, dataset_id, location)
    matching = next((t for t in tables if t["table_id"] == table_id), None)
    if matching is None:
        raise TableNotFoundError(project_id, dataset_id, table_id)

    columns = get_table_columns(client, project_id, dataset_id, table_id, location)
    bq_table = get_table_cached(client, f"{project_id}.{dataset_id}.{table_id}")

    return {
        **matching,
        "columns": columns,
        "labels": dict(bq_table.labels or {}),
        "description": bq_table.description,
    }
