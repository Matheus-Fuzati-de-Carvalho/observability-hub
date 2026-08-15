"""Queries do domínio pii. Única camada que fala com o client do BigQuery
— sql_builder.py monta o texto das queries (sem client), service.py
nunca vê SQL nem objetos do client além do que estas funções retornam.

Duplica (não importa) funções equivalentes de domains/quality/repository.py
— nenhum domínio deste projeto importa de outro (ver CLAUDE.md, domínios
isolados; mesma decisão já tomada em domains/lineage/repository.py).
"""

from google.api_core.exceptions import Forbidden
from google.cloud import bigquery

from observability_hub.core.exceptions import ProjectAccessDeniedError

# INFORMATION_SCHEMA.TABLES.table_type usa "VIEW" e "MATERIALIZED VIEW"
# (com espaço) — nenhum dos dois suporta TABLESAMPLE no BigQuery.
_VIEW_TABLE_TYPES = {"VIEW", "MATERIALIZED VIEW"}


def get_table_columns(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, location: str
) -> list[dict]:
    """Nome e tipo de cada coluna — pii não precisa de description nem
    is_nullable (diferente de catalog/quality), só o suficiente pra
    decidir elegibilidade de amostragem e heurística de nome."""
    query = f"""
        SELECT column_name, data_type
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
    return [{"column_name": row.column_name, "data_type": row.data_type} for row in rows]


def is_view(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, location: str
) -> bool:
    """VIEW e MATERIALIZED VIEW não suportam TABLESAMPLE no BigQuery — o
    sql_builder precisa saber disso antes de montar a query de scan."""
    query = f"""
        SELECT table_type
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLES`
        WHERE table_schema = @dataset_id AND table_name = @table_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("table_id", "STRING", table_id),
        ]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return bool(rows) and rows[0].table_type in _VIEW_TABLE_TYPES


def dry_run(client: bigquery.Client, project_id: str, sql: str) -> int:
    """Bytes que a query processaria, sem executar de fato
    (QueryJobConfig(dry_run=True) — exigido pelo endpoint /estimate)."""
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    try:
        job = client.query(sql, job_config=job_config)
    except Forbidden as exc:
        raise ProjectAccessDeniedError(project_id) from exc
    return job.total_bytes_processed


def execute_scan_query(client: bigquery.Client, project_id: str, sql: str, timeout: float) -> dict:
    """Query de scan é sempre uma única linha agregada — mesmo tabela com
    0 linhas amostradas retorna 1 linha com contagens zeradas."""
    try:
        rows = list(client.query(sql).result(timeout=timeout))
    except Forbidden as exc:
        raise ProjectAccessDeniedError(project_id) from exc
    row = rows[0]
    return dict(row.items())
