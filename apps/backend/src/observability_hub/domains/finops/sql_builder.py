"""Geração pura de SQL pra sugestão de tipo de coluna — nenhuma função
aqui toca o client do BigQuery (mesmo papel que domains/pii/sql_builder.py
e domains/quality/sql_builder.py).

Detecção via SAFE_CAST + COUNTIF: a API nunca vê o valor real da coluna,
só contagens agregadas — mesma garantia estrutural de privacidade do
domínio pii. Ver docs/specs/finops-column-types.md.
"""

# Ordem de prioridade: primeiro tipo com 100% de match no não-nulo
# amostrado vence. INT64 antes de FLOAT64 porque todo INT64 válido
# também é FLOAT64 válido — checar o mais estreito primeiro evita
# sugerir o tipo mais largo quando o mais estreito já serve. BOOL só
# aceita "true"/"false" no BigQuery (não "0"/"1", que já teriam batido
# em INT64 antes de chegar aqui).
CANDIDATE_TYPES: list[str] = ["INT64", "FLOAT64", "BOOL", "DATE", "DATETIME", "TIMESTAMP"]

# Bytes fixos de armazenamento por tipo (documentação de storage pricing
# do BigQuery) — usados pra comparar contra o tamanho médio da STRING
# atual e decidir se a troca de fato economiza (ver
# docs/specs/finops-column-types.md, "Fórmula de bytes").
TYPE_FIXED_BYTES: dict[str, int] = {
    "INT64": 8,
    "FLOAT64": 8,
    "BOOL": 1,
    "DATE": 8,
    "DATETIME": 8,
    "TIMESTAMP": 8,
}


def _non_null_alias(column_name: str) -> str:
    return f"{column_name}__non_null"


def _avg_bytes_alias(column_name: str) -> str:
    return f"{column_name}__avg_bytes"


def _match_alias(column_name: str, candidate_type: str) -> str:
    return f"{column_name}__{candidate_type}"


def build_scan_query(
    project_id: str,
    dataset_id: str,
    table_id: str,
    string_columns: list[str],
    sample_percent: float,
    is_view: bool,
) -> str | None:
    """Uma linha só, com todas as contagens agregadas de todas as
    colunas candidatas — mesmo padrão de build_scan_query em
    domains/pii/sql_builder.py. Por coluna: COUNTIF(non_null),
    AVG(BYTE_LENGTH) e COUNTIF(SAFE_CAST(...) IS NOT NULL) por tipo
    candidato.

    None se string_columns estiver vazio — nada pra amostrar, quem
    chama não deve executar/dry-run uma query sem nenhum SELECT.

    is_view=True omite TABLESAMPLE — VIEW e MATERIALIZED VIEW não
    suportam essa sintaxe no BigQuery (mesmo guard de
    domains/pii/sql_builder.py e domains/quality/sql_builder.py)."""
    if not string_columns:
        return None

    select_parts: list[str] = []
    for column_name in string_columns:
        ref = f"`{column_name}`"
        select_parts.append(f"COUNTIF({ref} IS NOT NULL) AS `{_non_null_alias(column_name)}`")
        select_parts.append(f"AVG(BYTE_LENGTH({ref})) AS `{_avg_bytes_alias(column_name)}`")
        for candidate_type in CANDIDATE_TYPES:
            alias = _match_alias(column_name, candidate_type)
            select_parts.append(
                f"COUNTIF(SAFE_CAST({ref} AS {candidate_type}) IS NOT NULL) AS `{alias}`"
            )

    select_clause = ",\n  ".join(select_parts)
    sample_clause = "" if is_view else f"\nTABLESAMPLE SYSTEM ({sample_percent} PERCENT)"
    return f"SELECT\n  {select_clause}\nFROM `{project_id}.{dataset_id}.{table_id}`{sample_clause}"
