"""Geração pura de SQL para o domínio pii — nenhuma função aqui toca o
client do BigQuery (mesmo papel que domains/quality/sql_builder.py).

O matching roda inteiramente em SQL via REGEXP_CONTAINS + COUNTIF: a API
nunca recebe um valor de coluna real, só contagens agregadas por
coluna/tipo — ver docs/specs/pii.md, "Garantia de privacidade
estrutural".
"""

# REGEXP_CONTAINS do BigQuery usa RE2 (sem lookahead/backreference).
# Padrões de formato apenas — sem validação de dígito verificador
# (CPF/CNPJ) nem algoritmo de Luhn (cartão), ver docs/specs/pii.md,
# "Fora do escopo".
PII_PATTERNS: dict[str, str] = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "cpf": r"\d{3}\.\d{3}\.\d{3}-\d{2}",
    "cnpj": r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}",
    "telefone_br": r"(\(\d{2}\)\s?)?9?\d{4}-\d{4}",
    "cep": r"\d{5}-\d{3}",
    "cartao_credito": r"\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}",
}

NAME_HEURISTIC_KEYWORDS: dict[str, list[str]] = {
    "email": ["email", "e_mail"],
    "cpf": ["cpf"],
    "cnpj": ["cnpj"],
    "telefone_br": ["telefone", "phone", "celular", "fone"],
    "cep": ["cep"],
    "cartao_credito": ["cartao", "cartão", "card_number", "num_cartao"],
}


def name_match_types(column_name: str) -> list[str]:
    """Tipos de PII cujo nome de coluna bate por substring
    (case-insensitive) com alguma keyword conhecida — grátis, roda antes
    (e independente) de qualquer amostragem."""
    lowered = column_name.lower()
    return [
        pii_type
        for pii_type, keywords in NAME_HEURISTIC_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]


def _non_null_alias(column_name: str) -> str:
    return f"{column_name}__non_null"


def _match_alias(column_name: str, pii_type: str) -> str:
    return f"{column_name}__{pii_type}"


def build_scan_query(
    project_id: str,
    dataset_id: str,
    table_id: str,
    string_columns: list[str],
    sample_percent: float,
    is_view: bool,
) -> str | None:
    """Uma linha só, com todas as contagens agregadas de todas as
    colunas candidatas — mesmo padrão de build_main_query em
    domains/quality/sql_builder.py. Por coluna: COUNTIF(non_null) +
    COUNTIF(REGEXP_CONTAINS(...)) por tipo de PII.

    None se string_columns estiver vazio — nada pra amostrar, quem chama
    não deve executar/dry-run uma query sem nenhum SELECT.

    is_view=True omite TABLESAMPLE (e ignora sample_percent) — VIEW e
    MATERIALIZED VIEW não suportam essa sintaxe no BigQuery (mesmo guard
    de domains/quality/sql_builder.py::build_main_query)."""
    if not string_columns:
        return None

    select_parts: list[str] = []
    for column_name in string_columns:
        ref = f"`{column_name}`"
        select_parts.append(f"COUNTIF({ref} IS NOT NULL) AS `{_non_null_alias(column_name)}`")
        for pii_type, pattern in PII_PATTERNS.items():
            alias = _match_alias(column_name, pii_type)
            select_parts.append(f"COUNTIF(REGEXP_CONTAINS({ref}, r'{pattern}')) AS `{alias}`")

    select_clause = ",\n  ".join(select_parts)
    sample_clause = "" if is_view else f"\nTABLESAMPLE SYSTEM ({sample_percent} PERCENT)"
    return f"SELECT\n  {select_clause}\nFROM `{project_id}.{dataset_id}.{table_id}`{sample_clause}"
