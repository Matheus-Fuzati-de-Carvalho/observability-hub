"""Queries do domínio freshness. Única camada que constrói SQL e interpreta
linhas cruas do INFORMATION_SCHEMA (e resultados de client.get_table()) —
service.py nunca vê SQL nem objetos do client do BigQuery além do que essas
funções retornam.

get_freshness_summary_by_dataset (visão de projeto) lê de
INFORMATION_SCHEMA.TABLE_STORAGE (custo $0, lag de até 24h). get_table_freshness
(visão de dataset) lê last_modified_time/size_bytes/row_count via
client.get_table() (tempo real, sem lag, custo $0) — ver core/bigquery.py.
"""

from google.cloud import bigquery

from observability_hub.core.bigquery import get_tables_metadata
from observability_hub.core.sla import hours_since, sla_status

# TABLE_STORAGE.table_type usa os mesmos valores brutos de TABLES ("BASE
# TABLE", "MATERIALIZED VIEW" com espaço); a API expõe os valores
# documentados na spec (freshness.md v1.1, mesmo vocabulário do catalog).
_RAW_TABLE_TYPE_TO_API = {
    "BASE TABLE": "TABLE",
    "VIEW": "VIEW",
    "EXTERNAL": "EXTERNAL",
    "MATERIALIZED VIEW": "MATERIALIZED_VIEW",
}


# TABLE_STORAGE.storage_last_modified_time pode ser null (metadados de
# storage ainda não propagados para uma tabela recém-criada/gravada) — sem o
# WHEN ... IS NULL explícito, TIMESTAMP_DIFF(NOW, NULL, HOUR) retorna NULL, a
# comparação NULL <= 12 nunca é TRUE, e a lógica de três valores do SQL cai
# no ELSE 'stale' por engano, classificando tabelas sem dado como as mais
# atrasadas possíveis.
def _sla_status_case_sql(timestamp_expr: str) -> str:
    hours_expr = f"TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), {timestamp_expr}, HOUR)"
    return f"""CASE
              WHEN {timestamp_expr} IS NULL THEN NULL
              WHEN {hours_expr} <= 12 THEN 'ok'
              WHEN {hours_expr} <= 24 THEN 'warning_12_24'
              WHEN {hours_expr} <= 48 THEN 'warning_24_48'
              WHEN {hours_expr} <= 168 THEN 'warning_48_7d'
              WHEN {hours_expr} <= 720 THEN 'warning_7d_1m'
              ELSE 'stale'
            END"""


def get_freshness_summary_by_dataset(
    client: bigquery.Client, project_id: str, regions: list[str]
) -> list[dict]:
    """Visão por projeto (GET /freshness/{project_id}), rodada uma vez por
    região — INFORMATION_SCHEMA é region-qualified. LEFT JOIN a partir de
    SCHEMATA (não de TABLE_STORAGE) para datasets vazios aparecerem com
    total_tables=0 em vez de sumirem da lista (spec, casos de borda)."""
    sla_status_sql = _sla_status_case_sql("ts.storage_last_modified_time")
    datasets: list[dict] = []
    for region in regions:
        query = f"""
            WITH per_table AS (
              SELECT
                s.schema_name  AS dataset_id,
                s.location,
                ts.table_name,
                {sla_status_sql} AS sla_status
              FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.SCHEMATA` s
              LEFT JOIN `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLE_STORAGE` ts
                ON ts.table_schema = s.schema_name
            )
            SELECT
              dataset_id,
              ANY_VALUE(location)                          AS location,
              COUNT(table_name)                             AS total_tables,
              COUNTIF(sla_status = 'ok')                    AS ok,
              COUNTIF(sla_status = 'warning_12_24')         AS warning_12_24,
              COUNTIF(sla_status = 'warning_24_48')         AS warning_24_48,
              COUNTIF(sla_status = 'warning_48_7d')         AS warning_48_7d,
              COUNTIF(sla_status = 'warning_7d_1m')         AS warning_7d_1m,
              COUNTIF(sla_status = 'stale')                 AS stale
            FROM per_table
            GROUP BY dataset_id
            ORDER BY dataset_id
        """
        rows = client.query(query).result()
        for row in rows:
            datasets.append(
                {
                    "dataset_id": row.dataset_id,
                    "location": row.location,
                    "total_tables": row.total_tables,
                    "ok": row.ok,
                    "warning_12_24": row.warning_12_24,
                    "warning_24_48": row.warning_24_48,
                    "warning_48_7d": row.warning_48_7d,
                    "warning_7d_1m": row.warning_7d_1m,
                    "stale": row.stale,
                }
            )
    return datasets


def get_table_freshness(
    client: bigquery.Client, project_id: str, dataset_id: str, location: str
) -> list[dict]:
    """Visão por dataset (GET /freshness/{project_id}/datasets/{dataset_id}).
    Lista as tabelas via INFORMATION_SCHEMA.TABLES e busca
    last_modified_time/size_bytes/row_count via client.get_table() (uma
    chamada por tabela, em paralelo, cacheada 5min em core.bigquery) em vez
    de INFORMATION_SCHEMA.TABLE_STORAGE — TABLE_STORAGE tem lag de até 24h,
    client.get_table() é tempo real, base do cálculo de SLA. Se o dataset
    existe mas não tem tabelas, retorna lista vazia (dataset_id já foi
    validado antes via resolve_dataset_region, então "vazio" aqui é dado
    real, não erro)."""
    query = f"""
        SELECT table_name AS table_id, table_type
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLES`
        WHERE table_schema = @dataset_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id)]
    )
    rows = list(client.query(query, job_config=job_config).result())

    table_refs = [f"{project_id}.{dataset_id}.{row.table_id}" for row in rows]
    metadata_by_ref = get_tables_metadata(client, table_refs)

    tables = []
    for row in rows:
        bq_table = metadata_by_ref.get(f"{project_id}.{dataset_id}.{row.table_id}")
        modified = bq_table.modified if bq_table is not None else None
        hours_since_update = hours_since(modified)
        tables.append(
            {
                "table_id": row.table_id,
                "table_type": _RAW_TABLE_TYPE_TO_API.get(row.table_type, row.table_type),
                "last_modified_time": modified,
                "hours_since_update": hours_since_update,
                "sla_status": sla_status(hours_since_update),
                "size_bytes": bq_table.num_bytes if bq_table is not None else None,
                "row_count": bq_table.num_rows if bq_table is not None else None,
            }
        )
    tables.sort(key=lambda t: (t["hours_since_update"] is None, -(t["hours_since_update"] or 0)))
    return tables
