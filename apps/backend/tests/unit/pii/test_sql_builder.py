from observability_hub.domains.pii import sql_builder

# --- name_match_types -------------------------------------------------------


def test_name_match_types_matches_each_known_keyword():
    assert sql_builder.name_match_types("email_cliente") == ["email"]
    assert sql_builder.name_match_types("cpf_titular") == ["cpf"]
    assert sql_builder.name_match_types("cnpj_empresa") == ["cnpj"]
    assert sql_builder.name_match_types("telefone_contato") == ["telefone_br"]
    assert sql_builder.name_match_types("cep_entrega") == ["cep"]
    assert sql_builder.name_match_types("numero_cartao") == ["cartao_credito"]


def test_name_match_types_is_case_insensitive():
    assert sql_builder.name_match_types("EMAIL_CLIENTE") == ["email"]
    assert sql_builder.name_match_types("Cpf") == ["cpf"]


def test_name_match_types_returns_multiple_matches():
    result = sql_builder.name_match_types("cpf_ou_cnpj")
    assert set(result) == {"cpf", "cnpj"}


def test_name_match_types_returns_empty_for_unrelated_column():
    assert sql_builder.name_match_types("total_pedidos") == []


# --- build_scan_query --------------------------------------------------------


def test_build_scan_query_returns_none_for_no_string_columns():
    sql = sql_builder.build_scan_query("proj", "RAW", "clientes", [], 10.0, is_view=False)
    assert sql is None


def test_build_scan_query_includes_non_null_and_pattern_counts_per_column():
    sql = sql_builder.build_scan_query("proj", "RAW", "clientes", ["email"], 10.0, is_view=False)

    assert sql is not None
    assert "COUNTIF(`email` IS NOT NULL) AS `email__non_null`" in sql
    for pii_type in sql_builder.PII_PATTERNS:
        assert f"AS `email__{pii_type}`" in sql
    assert "REGEXP_CONTAINS(`email`, r'" in sql
    assert "FROM `proj.RAW.clientes`" in sql


def test_build_scan_query_includes_tablesample_when_not_view():
    sql = sql_builder.build_scan_query("proj", "RAW", "clientes", ["email"], 12.5, is_view=False)
    assert "TABLESAMPLE SYSTEM (12.5 PERCENT)" in sql


def test_build_scan_query_omits_tablesample_when_view():
    sql = sql_builder.build_scan_query("proj", "RAW", "clientes", ["email"], 12.5, is_view=True)
    assert "TABLESAMPLE" not in sql


def test_build_scan_query_covers_every_candidate_column():
    sql = sql_builder.build_scan_query(
        "proj", "RAW", "clientes", ["email", "telefone"], 10.0, is_view=False
    )
    assert "`email__non_null`" in sql
    assert "`telefone__non_null`" in sql
