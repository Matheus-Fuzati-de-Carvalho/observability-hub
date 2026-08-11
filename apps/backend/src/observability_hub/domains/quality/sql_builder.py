"""Geração pura de SQL para o domínio quality (profiling) — nenhuma função
aqui toca o client do BigQuery. repository.py chama estas funções para
montar as queries e usa column_field_aliases() para saber como reler o
resultado, evitando duas fontes de verdade para o nome dos aliases.
"""

from dataclasses import dataclass

from observability_hub.domains.quality.schemas import Granularity, UniquenessMethod

# Tipos numéricos do BigQuery (INFORMATION_SCHEMA.COLUMNS.data_type já vem
# nesses nomes canônicos) — determinam se AVG/STDDEV/CV se aplicam.
_NUMERIC_TYPES = {"INT64", "FLOAT64", "NUMERIC", "BIGNUMERIC"}


@dataclass(frozen=True)
class ProfileableColumn:
    name: str
    data_type: str


def is_numeric_type(data_type: str) -> bool:
    return data_type.upper() in _NUMERIC_TYPES


def is_excluded_type(data_type: str) -> bool:
    """STRUCT/ARRAY são representados em INFORMATION_SCHEMA.COLUMNS.data_type
    como texto literal "STRUCT<...>"/"ARRAY<...>" — sem função dedicada pra
    isso no BigQuery, checar o prefixo é a forma correta."""
    upper = data_type.upper()
    return upper.startswith(("ARRAY<", "STRUCT<"))


def _distinct_key(method: UniquenessMethod) -> str:
    return "approx_distinct" if method == UniquenessMethod.APPROX else "exact_distinct"


def _distinct_expr(column_ref: str, method: UniquenessMethod) -> str:
    if method == UniquenessMethod.APPROX:
        return f"APPROX_COUNT_DISTINCT({column_ref})"
    return f"COUNT(DISTINCT {column_ref})"


def column_field_aliases(
    column_name: str, data_type: str, method: UniquenessMethod
) -> dict[str, str]:
    """Nomes de alias usados tanto pra montar o SELECT quanto pra reler a
    linha de resultado — chave lógica (count_filled, distinct, min, max,
    avg, stddev) -> nome do alias SQL de fato."""
    base = f"{column_name}__"
    aliases = {
        "count_filled": f"{base}count_filled",
        "distinct": f"{base}{_distinct_key(method)}",
        "min": f"{base}min",
        "max": f"{base}max",
    }
    if is_numeric_type(data_type):
        aliases["avg"] = f"{base}avg"
        aliases["stddev"] = f"{base}stddev"
    return aliases


def _date_filter_sql(date_column: str | None, date_window_days: int | None) -> str:
    """Filtro temporal só é aplicado se as duas informações estiverem
    presentes — date_column sozinho sem janela (ou vice-versa) não dá pra
    montar um filtro válido."""
    if not date_column or not date_window_days:
        return ""
    return f"\nWHERE `{date_column}` >= DATE_SUB(CURRENT_DATE(), INTERVAL {date_window_days} DAY)"


def build_main_query(
    project_id: str,
    dataset_id: str,
    table_id: str,
    columns: list[ProfileableColumn],
    sample_percent: float,
    uniqueness_method: UniquenessMethod,
    date_column: str | None,
    date_window_days: int | None,
    is_view: bool = False,
) -> str:
    """Query principal (spec, "Query principal") — uma linha só, com todas as
    métricas agregadas de todas as colunas. _approx_distinct_rows (via
    TO_JSON_STRING(t)) é calculado aqui também, não numa query separada —
    mais barato que reler a tabela de novo, e é o motivo do alias `t` no
    FROM (ver spec, "Registros duplicados estimados").

    is_view=True omite o TABLESAMPLE (e ignora sample_percent) — VIEW e
    MATERIALIZED VIEW não suportam essa sintaxe no BigQuery."""
    select_parts = [
        "COUNT(*) AS _total_sampled_rows",
        "APPROX_COUNT_DISTINCT(TO_JSON_STRING(t)) AS _approx_distinct_rows",
    ]
    for col in columns:
        ref = f"`{col.name}`"
        aliases = column_field_aliases(col.name, col.data_type, uniqueness_method)
        select_parts.append(f"COUNT({ref}) AS `{aliases['count_filled']}`")
        select_parts.append(f"{_distinct_expr(ref, uniqueness_method)} AS `{aliases['distinct']}`")
        select_parts.append(f"MIN({ref}) AS `{aliases['min']}`")
        select_parts.append(f"MAX({ref}) AS `{aliases['max']}`")
        if "avg" in aliases:
            select_parts.append(f"AVG(CAST({ref} AS FLOAT64)) AS `{aliases['avg']}`")
            select_parts.append(f"STDDEV(CAST({ref} AS FLOAT64)) AS `{aliases['stddev']}`")

    select_clause = ",\n  ".join(select_parts)
    where_clause = _date_filter_sql(date_column, date_window_days)
    sample_clause = "" if is_view else f"\nTABLESAMPLE SYSTEM ({sample_percent} PERCENT)"
    return (
        f"SELECT\n"
        f"  {select_clause}\n"
        f"FROM `{project_id}.{dataset_id}.{table_id}` AS t"
        f"{sample_clause}"
        f"{where_clause}"
    )


def build_top_n_query(
    project_id: str,
    dataset_id: str,
    table_id: str,
    column_name: str,
    sample_percent: float,
    date_column: str | None,
    date_window_days: int | None,
    is_view: bool = False,
) -> str:
    """Top N valores (spec) — só chamada para colunas com distinct_count < 50
    (decisão tomada por quem chama, não por esta função).

    is_view=True omite o TABLESAMPLE (e ignora sample_percent), pelo mesmo
    motivo de build_main_query."""
    where_clause = _date_filter_sql(date_column, date_window_days)
    sample_clause = "" if is_view else f"\nTABLESAMPLE SYSTEM ({sample_percent} PERCENT)"
    return (
        f"SELECT `{column_name}` AS value, COUNT(*) AS count\n"
        f"FROM `{project_id}.{dataset_id}.{table_id}`"
        f"{sample_clause}"
        f"{where_clause}\n"
        f"GROUP BY 1\n"
        f"ORDER BY count DESC\n"
        f"LIMIT 10"
    )


def _period_expr(date_column: str, date_column_type: str, granularity: Granularity) -> str:
    """DATE_TRUNC só aceita DATE; TIMESTAMP/DATETIME precisam de
    TIMESTAMP_TRUNC/DATETIME_TRUNC — não são intercambiáveis no BigQuery."""
    col_ref = f"`{date_column}`"
    upper = date_column_type.upper()
    if upper == "TIMESTAMP":
        trunc_fn = "TIMESTAMP_TRUNC"
    elif upper == "DATETIME":
        trunc_fn = "DATETIME_TRUNC"
    else:
        trunc_fn = "DATE_TRUNC"

    if granularity == Granularity.DAY:
        if upper in ("TIMESTAMP", "DATETIME"):
            return f"DATE({col_ref})"
        return col_ref
    part = "WEEK" if granularity == Granularity.WEEK else "MONTH"
    return f"{trunc_fn}({col_ref}, {part})"


def build_null_distribution_query(
    project_id: str,
    dataset_id: str,
    table_id: str,
    column_name: str,
    date_column: str,
    date_column_type: str,
    date_window_days: int,
    granularity: Granularity,
) -> str:
    period_expr = _period_expr(date_column, date_column_type, granularity)
    return (
        f"SELECT\n"
        f"  {period_expr} AS period,\n"
        f"  COUNTIF(`{column_name}` IS NULL) AS null_count,\n"
        f"  COUNT(*) AS total_rows\n"
        f"FROM `{project_id}.{dataset_id}.{table_id}`\n"
        f"WHERE `{date_column}` >= DATE_SUB(CURRENT_DATE(), INTERVAL {date_window_days} DAY)\n"
        f"GROUP BY period\n"
        f"ORDER BY period"
    )
