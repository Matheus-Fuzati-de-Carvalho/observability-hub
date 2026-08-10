"""Queries do domínio catalog. Única camada que constrói SQL e interpreta
linhas cruas do INFORMATION_SCHEMA — service.py nunca vê SQL nem objetos do
client do BigQuery além do que essas funções retornam.
"""

from google.cloud import bigquery

from observability_hub.core.exceptions import DatasetNotFoundError, TableNotFoundError

# INFORMATION_SCHEMA.TABLES usa "BASE TABLE" e "MATERIALIZED VIEW" (com
# espaço); a API expõe os valores documentados na spec (catalog.md v1.2).
_RAW_TABLE_TYPE_TO_API = {
    "BASE TABLE": "TABLE",
    "VIEW": "VIEW",
    "EXTERNAL": "EXTERNAL",
    "MATERIALIZED VIEW": "MATERIALIZED_VIEW",
}
_API_TABLE_TYPE_TO_RAW = {v: k for k, v in _RAW_TABLE_TYPE_TO_API.items()}


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


def resolve_dataset_region(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    candidate_regions: list[str],
) -> str:
    """Descobre em qual região está um dataset_id. Os endpoints de tabelas não
    recebem region (spec v1.2) — dataset_id é único por projeto independente
    da região, então basta encontrar a primeira região candidata que bate."""
    for region in candidate_regions:
        query = f"""
            SELECT location
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.SCHEMATA`
            WHERE schema_name = @dataset_id
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id)]
        )
        rows = list(client.query(query, job_config=job_config).result())
        if rows:
            return region
    raise DatasetNotFoundError(project_id, dataset_id)


def _row_to_table_dict(row, location: str) -> dict:
    clustering_columns = list(row.clustering_columns or [])
    partition_column = row.partition_column
    return {
        "table_id": row.table_name,
        "table_type": _RAW_TABLE_TYPE_TO_API.get(row.table_type, row.table_type),
        "creation_time": row.creation_time,
        "last_modified_time": row.last_modified_time,
        "size_bytes": row.size_bytes,
        "size_gb": _bytes_to_gb(row.size_bytes),
        "row_count": row.row_count,
        "column_count": row.column_count,
        "is_partitioned": partition_column is not None,
        "partition_column": partition_column,
        "is_clustered": len(clustering_columns) > 0,
        "clustering_columns": clustering_columns,
        "location": location,
    }


_MULTI_REGIONS = {"US", "EU"}


def get_tables_summary(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    location: str,
    table_type: str | None = None,
) -> list[dict]:
    """Query 3 da spec, estendida para derivar is_clustered/clustering_columns
    de COLUMNS.clustering_ordinal_position — a query documentada não fazia
    isso, mas o response da spec exige esses campos (divergência resolvida
    conforme combinado).

    INFORMATION_SCHEMA.TABLE_PARTITIONS não existe nas multi-regiões US/EU
    (só em regiões específicas, ex: us-central1) — nessas multi-regiões o
    JOIN é omitido e partition_column sempre retorna null."""
    query_params = [bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id)]
    where_extra = ""
    if table_type is not None:
        raw_type = _API_TABLE_TYPE_TO_RAW.get(table_type, table_type)
        where_extra = " AND t.table_type = @table_type"
        query_params.append(bigquery.ScalarQueryParameter("table_type", "STRING", raw_type))

    is_multi_region = location.upper() in _MULTI_REGIONS
    if is_multi_region:
        partition_join = ""
        partition_column_select = (
            "CAST(NULL AS STRING)                              AS partition_column,"
        )
    else:
        partition_join = f"""
        LEFT JOIN `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLE_PARTITIONS` tp
          ON tp.table_name = t.table_name AND tp.table_schema = t.table_schema"""
        partition_column_select = (
            "MAX(tp.partition_column)                          AS partition_column,"
        )

    query = f"""
        WITH columns_agg AS (
          SELECT
            table_schema,
            table_name,
            COUNT(column_name)                                       AS column_count,
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
          ts.last_modified_time,
          ts.total_rows                                    AS row_count,
          ts.total_logical_bytes                            AS size_bytes,
          ANY_VALUE(COALESCE(ca.column_count, 0))           AS column_count,
          {partition_column_select}
          ANY_VALUE(COALESCE(ca.clustering_columns, []))    AS clustering_columns
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLES` t
        LEFT JOIN `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLE_STORAGE` ts
          ON ts.table_name = t.table_name AND ts.table_schema = t.table_schema
        LEFT JOIN columns_agg ca
          ON ca.table_name = t.table_name AND ca.table_schema = t.table_schema{partition_join}
        WHERE t.table_schema = @dataset_id{where_extra}
        GROUP BY 1, 2, 3, 4, 5, 6
        ORDER BY size_bytes DESC NULLS LAST
    """
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    rows = client.query(query, job_config=job_config).result()
    return [_row_to_table_dict(row, location) for row in rows]


def get_table_columns(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    location: str,
) -> list[dict]:
    query = f"""
        SELECT column_name, data_type, is_nullable, description
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_schema = @dataset_id AND table_name = @table_id
        ORDER BY ordinal_position
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
    (metadados, custo $0), leitura muito mais confiável."""
    tables = get_tables_summary(client, project_id, dataset_id, location)
    matching = next((t for t in tables if t["table_id"] == table_id), None)
    if matching is None:
        raise TableNotFoundError(project_id, dataset_id, table_id)

    columns = get_table_columns(client, project_id, dataset_id, table_id, location)
    bq_table = client.get_table(f"{project_id}.{dataset_id}.{table_id}")

    return {
        **matching,
        "columns": columns,
        "labels": dict(bq_table.labels or {}),
        "description": bq_table.description,
    }
