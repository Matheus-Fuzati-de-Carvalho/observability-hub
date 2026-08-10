"""Queries do domínio freshness. Única camada que constrói SQL e interpreta
linhas cruas do INFORMATION_SCHEMA — service.py nunca vê SQL nem objetos do
client do BigQuery além do que essas funções retornam.

Toda leitura vem de INFORMATION_SCHEMA.TABLE_STORAGE (spec v1.1, custo $0).
"""

from google.cloud import bigquery

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
    Sem JOIN — se o dataset existe mas não tem tabelas em TABLE_STORAGE
    ainda, retorna lista vazia (dataset_id já foi validado antes via
    resolve_dataset_region, então "vazio" aqui é dado real, não erro)."""
    sla_status_sql = _sla_status_case_sql("storage_last_modified_time")
    query = f"""
        SELECT
          table_name                                        AS table_id,
          table_type,
          storage_last_modified_time                        AS last_modified_time,
          TIMESTAMP_DIFF(
            CURRENT_TIMESTAMP(), storage_last_modified_time, HOUR
          )                                                  AS hours_since_update,
          total_logical_bytes                                AS size_bytes,
          total_rows                                          AS row_count,
          {sla_status_sql} AS sla_status
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLE_STORAGE`
        WHERE table_schema = @dataset_id
        ORDER BY hours_since_update DESC NULLS LAST
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id)]
    )
    rows = client.query(query, job_config=job_config).result()
    return [
        {
            "table_id": row.table_id,
            "table_type": _RAW_TABLE_TYPE_TO_API.get(row.table_type, row.table_type),
            "last_modified_time": row.last_modified_time,
            "hours_since_update": row.hours_since_update,
            "sla_status": row.sla_status,
            "size_bytes": row.size_bytes,
            "row_count": row.row_count,
        }
        for row in rows
    ]
