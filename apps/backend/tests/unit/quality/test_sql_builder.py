from observability_hub.domains.quality import sql_builder
from observability_hub.domains.quality.schemas import Granularity, UniquenessMethod
from observability_hub.domains.quality.sql_builder import ProfileableColumn


def test_is_numeric_type_true_for_known_numeric_types():
    for dtype in ("INT64", "FLOAT64", "NUMERIC", "BIGNUMERIC", "int64", "Float64"):
        assert sql_builder.is_numeric_type(dtype) is True


def test_is_numeric_type_false_for_non_numeric_types():
    for dtype in ("STRING", "BOOL", "DATE", "TIMESTAMP", "BYTES"):
        assert sql_builder.is_numeric_type(dtype) is False


def test_is_excluded_type_true_for_struct_and_array():
    assert sql_builder.is_excluded_type("ARRAY<STRING>") is True
    assert sql_builder.is_excluded_type("STRUCT<x INT64, y STRING>") is True
    assert sql_builder.is_excluded_type("array<int64>") is True


def test_is_excluded_type_false_for_scalar_types():
    for dtype in ("STRING", "INT64", "FLOAT64", "DATE", "BOOL"):
        assert sql_builder.is_excluded_type(dtype) is False


def test_column_field_aliases_uses_approx_distinct_alias_for_approx_method():
    aliases = sql_builder.column_field_aliases("lead_status", "STRING", UniquenessMethod.APPROX)
    assert aliases["distinct"] == "lead_status__approx_distinct"
    assert aliases["count_filled"] == "lead_status__count_filled"
    assert aliases["min"] == "lead_status__min"
    assert aliases["max"] == "lead_status__max"
    assert "avg" not in aliases
    assert "stddev" not in aliases


def test_column_field_aliases_uses_exact_distinct_alias_for_exact_method():
    aliases = sql_builder.column_field_aliases("lead_status", "STRING", UniquenessMethod.EXACT)
    assert aliases["distinct"] == "lead_status__exact_distinct"


def test_column_field_aliases_includes_avg_stddev_for_numeric_columns():
    aliases = sql_builder.column_field_aliases("revenue", "FLOAT64", UniquenessMethod.APPROX)
    assert aliases["avg"] == "revenue__avg"
    assert aliases["stddev"] == "revenue__stddev"


def test_column_field_aliases_omits_avg_stddev_for_string_columns():
    aliases = sql_builder.column_field_aliases("email", "STRING", UniquenessMethod.APPROX)
    assert "avg" not in aliases
    assert "stddev" not in aliases


# --- build_main_query ---------------------------------------------------


def test_build_main_query_includes_total_sampled_rows_and_duplicate_detection():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", [], 100, UniquenessMethod.APPROX, None, None
    )
    assert "COUNT(*) AS _total_sampled_rows" in sql
    assert "APPROX_COUNT_DISTINCT(TO_JSON_STRING(t)) AS _approx_distinct_rows" in sql
    assert "FROM `proj.RAW.leads` AS t" in sql


def test_build_main_query_applies_tablesample_with_given_percent():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", [], 10, UniquenessMethod.APPROX, None, None
    )
    assert "TABLESAMPLE SYSTEM (10 PERCENT)" in sql


def test_build_main_query_omits_where_clause_without_date_filter():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", [], 100, UniquenessMethod.APPROX, None, None
    )
    assert "WHERE" not in sql


def test_build_main_query_omits_where_clause_when_only_date_column_given():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", [], 100, UniquenessMethod.APPROX, "date", None
    )
    assert "WHERE" not in sql


def test_build_main_query_omits_where_clause_when_only_window_given():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", [], 100, UniquenessMethod.APPROX, None, 30
    )
    assert "WHERE" not in sql


def test_build_main_query_includes_where_clause_when_both_date_params_given():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", [], 100, UniquenessMethod.APPROX, "date", 365
    )
    assert "WHERE `date` >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)" in sql


def test_build_main_query_string_column_uses_approx_count_distinct_and_no_avg():
    columns = [ProfileableColumn("lead_status", "STRING")]
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", columns, 100, UniquenessMethod.APPROX, None, None
    )
    assert "COUNT(`lead_status`) AS `lead_status__count_filled`" in sql
    assert "APPROX_COUNT_DISTINCT(`lead_status`) AS `lead_status__approx_distinct`" in sql
    assert "MIN(`lead_status`) AS `lead_status__min`" in sql
    assert "MAX(`lead_status`) AS `lead_status__max`" in sql
    assert "lead_status__avg" not in sql
    assert "lead_status__stddev" not in sql


def test_build_main_query_string_column_uses_exact_count_distinct_when_requested():
    columns = [ProfileableColumn("lead_status", "STRING")]
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", columns, 100, UniquenessMethod.EXACT, None, None
    )
    assert "COUNT(DISTINCT `lead_status`) AS `lead_status__exact_distinct`" in sql
    assert "APPROX_COUNT_DISTINCT(`lead_status`)" not in sql


def test_build_main_query_numeric_column_includes_avg_and_stddev_with_cast():
    columns = [ProfileableColumn("revenue", "FLOAT64")]
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", columns, 100, UniquenessMethod.APPROX, None, None
    )
    assert "AVG(CAST(`revenue` AS FLOAT64)) AS `revenue__avg`" in sql
    assert "STDDEV(CAST(`revenue` AS FLOAT64)) AS `revenue__stddev`" in sql


def test_build_main_query_multiple_columns_each_get_own_select_expressions():
    columns = [ProfileableColumn("lead_status", "STRING"), ProfileableColumn("revenue", "FLOAT64")]
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", columns, 100, UniquenessMethod.APPROX, None, None
    )
    assert "lead_status__count_filled" in sql
    assert "revenue__count_filled" in sql
    assert "revenue__avg" in sql
    assert "lead_status__avg" not in sql


def test_build_main_query_omits_tablesample_for_view():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "sales_view", [], 50, UniquenessMethod.APPROX, None, None, is_view=True
    )
    assert "TABLESAMPLE" not in sql
    assert "FROM `proj.RAW.sales_view` AS t" in sql


def test_build_main_query_defaults_to_not_a_view():
    sql = sql_builder.build_main_query(
        "proj", "RAW", "leads", [], 100, UniquenessMethod.APPROX, None, None
    )
    assert "TABLESAMPLE SYSTEM (100 PERCENT)" in sql


# --- build_top_n_query ----------------------------------------------------


def test_build_top_n_query_matches_spec_shape():
    sql = sql_builder.build_top_n_query("proj", "RAW", "leads", "lead_status", 100, None, None)
    assert "SELECT `lead_status` AS value, COUNT(*) AS count" in sql
    assert "FROM `proj.RAW.leads`" in sql
    assert "TABLESAMPLE SYSTEM (100 PERCENT)" in sql
    assert "GROUP BY 1" in sql
    assert "ORDER BY count DESC" in sql
    assert "LIMIT 10" in sql
    assert "WHERE" not in sql


def test_build_top_n_query_includes_date_filter_when_provided():
    sql = sql_builder.build_top_n_query("proj", "RAW", "leads", "lead_status", 10, "date", 365)
    assert "WHERE `date` >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)" in sql


def test_build_top_n_query_has_no_table_alias():
    """Diferente da query principal, não precisa de TO_JSON_STRING(t)."""
    sql = sql_builder.build_top_n_query("proj", "RAW", "leads", "lead_status", 100, None, None)
    assert "AS t" not in sql


def test_build_top_n_query_omits_tablesample_for_view():
    sql = sql_builder.build_top_n_query(
        "proj", "RAW", "sales_view", "region", 50, None, None, is_view=True
    )
    assert "TABLESAMPLE" not in sql
    assert "FROM `proj.RAW.sales_view`" in sql


# --- build_null_distribution_query ----------------------------------------


def test_build_null_distribution_query_date_type_uses_column_directly_for_day():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "signup_date", "DATE", 30, Granularity.DAY
    )
    assert "SELECT\n  `signup_date` AS period" in sql
    assert "DATE_TRUNC" not in sql
    assert "COUNTIF(`email` IS NULL) AS null_count" in sql
    assert "WHERE `signup_date` >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)" in sql


def test_build_null_distribution_query_timestamp_type_uses_date_cast_for_day():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "created_at", "TIMESTAMP", 30, Granularity.DAY
    )
    assert "DATE(`created_at`) AS period" in sql


def test_build_null_distribution_query_datetime_type_uses_date_cast_for_day():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "created_at", "DATETIME", 30, Granularity.DAY
    )
    assert "DATE(`created_at`) AS period" in sql


def test_build_null_distribution_query_date_type_uses_date_trunc_for_week():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "signup_date", "DATE", 30, Granularity.WEEK
    )
    assert "DATE_TRUNC(`signup_date`, WEEK) AS period" in sql


def test_build_null_distribution_query_date_type_uses_date_trunc_for_month():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "signup_date", "DATE", 30, Granularity.MONTH
    )
    assert "DATE_TRUNC(`signup_date`, MONTH) AS period" in sql


def test_build_null_distribution_query_timestamp_type_uses_timestamp_trunc_for_week():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "created_at", "TIMESTAMP", 30, Granularity.WEEK
    )
    assert "TIMESTAMP_TRUNC(`created_at`, WEEK) AS period" in sql


def test_build_null_distribution_query_datetime_type_uses_datetime_trunc_for_month():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "created_at", "DATETIME", 30, Granularity.MONTH
    )
    assert "DATETIME_TRUNC(`created_at`, MONTH) AS period" in sql


def test_build_null_distribution_query_lowercase_data_type_still_resolves_trunc_family():
    sql = sql_builder.build_null_distribution_query(
        "proj", "RAW", "leads", "email", "created_at", "timestamp", 30, Granularity.WEEK
    )
    assert "TIMESTAMP_TRUNC(`created_at`, WEEK) AS period" in sql
