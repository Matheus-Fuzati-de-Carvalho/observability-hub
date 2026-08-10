"""Queries do domínio quality. Única camada que fala com o client do BigQuery
— sql_builder.py monta o texto das queries (sem client), service.py nunca
vê SQL nem objetos do client além do que estas funções retornam.
"""

import datetime as dt
from decimal import Decimal

from google.cloud import bigquery

# Tipos de coluna aceitos como "coluna de data" para filtro temporal e
# null-distribution — os únicos com os quais DATE_SUB/DATE_TRUNC/
# TIMESTAMP_TRUNC/DATETIME_TRUNC fazem sentido.
DATE_COLUMN_TYPES = {"DATE", "DATETIME", "TIMESTAMP"}


def _to_jsonable_scalar(value: object) -> str | int | float | bool | None:
    """MIN/MAX podem vir em qualquer tipo do BigQuery. int/float/bool/str já
    são JSON-nativos; qualquer outra coisa (DATE, DATETIME, TIMESTAMP,
    NUMERIC/Decimal, BYTES...) vira string — evita um union frágil no
    schema Pydantic e ainda serve às regras de tipo lógico inferido, que já
    operam sobre string (ex: "min ou max contém @")."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dt.date | dt.datetime):
        return value.isoformat()
    return str(value)


def get_table_columns(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, location: str
) -> list[dict]:
    """Lista de colunas com tipo — não reaproveita catalog.get_table_columns
    porque profiling não precisa de description e precisa do data_type bruto
    (pra decidir exclusão de STRUCT/ARRAY e elegibilidade de CAST numérico),
    uma necessidade suficientemente diferente pra não valer a pena
    compartilhar a query entre os dois domínios."""
    query = f"""
        SELECT column_name, data_type, is_nullable
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
            "is_nullable": row.is_nullable == "YES",
        }
        for row in rows
    ]


def get_total_table_rows(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, location: str
) -> int | None:
    """total_rows de TABLE_STORAGE (metadado, custo $0) — nunca um COUNT(*)
    sem amostragem, que cobraria pela tabela inteira."""
    query = f"""
        SELECT total_rows
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLE_STORAGE`
        WHERE table_schema = @dataset_id AND table_name = @table_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("table_id", "STRING", table_id),
        ]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return rows[0].total_rows if rows else None


def dry_run(client: bigquery.Client, sql: str) -> int:
    """Bytes que a query processaria, sem executar de fato
    (QueryJobConfig(dry_run=True) — a spec exige isso pro /estimate)."""
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    return job.total_bytes_processed


def execute_main_query(client: bigquery.Client, sql: str, timeout: float) -> dict:
    """Query principal é sempre uma única linha agregada — mesmo tabela com
    0 linhas retorna 1 linha com contagens zeradas (COUNT(*) de nada é 0,
    não "sem linha")."""
    rows = list(client.query(sql).result(timeout=timeout))
    row = rows[0]
    return {key: _to_jsonable_scalar(value) for key, value in row.items()}


def execute_top_n_query(client: bigquery.Client, sql: str, timeout: float) -> list[dict]:
    rows = client.query(sql).result(timeout=timeout)
    return [{"value": _to_jsonable_scalar(row.value), "count": row.count} for row in rows]


def execute_null_distribution_query(
    client: bigquery.Client, sql: str, timeout: float
) -> list[dict]:
    rows = client.query(sql).result(timeout=timeout)
    return [
        {
            "period": _to_jsonable_scalar(row.period),
            "null_count": row.null_count,
            "total_rows": row.total_rows,
        }
        for row in rows
    ]
