from observability_hub.domains.finops import sql_builder


def test_build_scan_query_returns_none_for_empty_columns():
    assert sql_builder.build_scan_query("proj", "RAW", "t", [], 10, False) is None


def test_build_scan_query_includes_non_null_avg_bytes_and_type_match_aliases():
    sql = sql_builder.build_scan_query("proj", "RAW", "crm_leads", ["customer_id"], 10, False)

    assert sql is not None
    assert "`customer_id__non_null`" in sql
    assert "`customer_id__avg_bytes`" in sql
    for candidate_type in sql_builder.CANDIDATE_TYPES:
        assert f"`customer_id__{candidate_type}`" in sql
        assert f"SAFE_CAST(`customer_id` AS {candidate_type})" in sql


def test_build_scan_query_includes_tablesample_when_not_view():
    sql = sql_builder.build_scan_query("proj", "RAW", "t", ["c"], 15, False)

    assert sql is not None
    assert "TABLESAMPLE SYSTEM (15 PERCENT)" in sql


def test_build_scan_query_omits_tablesample_for_view():
    sql = sql_builder.build_scan_query("proj", "RAW", "t", ["c"], 15, True)

    assert sql is not None
    assert "TABLESAMPLE" not in sql


def test_build_scan_query_covers_multiple_columns():
    sql = sql_builder.build_scan_query("proj", "RAW", "t", ["a", "b"], 10, False)

    assert sql is not None
    assert "`a__non_null`" in sql
    assert "`b__non_null`" in sql


def test_candidate_types_priority_narrowest_first():
    # INT64 antes de FLOAT64 (todo INT64 válido também é FLOAT64 válido —
    # checar o mais estreito primeiro evita sugerir o tipo mais largo).
    assert sql_builder.CANDIDATE_TYPES.index("INT64") < sql_builder.CANDIDATE_TYPES.index("FLOAT64")


def test_type_fixed_bytes_covers_all_candidate_types():
    assert set(sql_builder.TYPE_FIXED_BYTES) == set(sql_builder.CANDIDATE_TYPES)
