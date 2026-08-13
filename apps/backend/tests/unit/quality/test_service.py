from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import (
    InvalidDateColumnError,
    InvalidSamplePercentError,
    ProfilingTimeoutError,
    TableNotFoundError,
)
from observability_hub.domains.quality import service
from observability_hub.domains.quality.schemas import (
    Granularity,
    InferredLogicalType,
    ProfilingRequest,
    QualityFlag,
    UniquenessMethod,
)


def _fake_client() -> MagicMock:
    return MagicMock(name="bigquery.Client")


def _stub_region_resolution(monkeypatch, location="US", is_view=False):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: location,
    )
    monkeypatch.setattr(
        service.repository,
        "is_view",
        lambda client, project_id, dataset_id, table_id, location: is_view,
    )


# --- validation helpers ----------------------------------------------------


def test_validate_sample_percent_raises_below_one():
    with pytest.raises(InvalidSamplePercentError):
        service._validate_sample_percent(0.5)


def test_validate_sample_percent_accepts_one_and_above():
    service._validate_sample_percent(1)
    service._validate_sample_percent(100)


def test_split_columns_separates_struct_array_from_profileable():
    raw = [
        {"column_name": "id", "data_type": "INT64", "is_nullable": False},
        {"column_name": "tags", "data_type": "ARRAY<STRING>", "is_nullable": True},
        {"column_name": "meta", "data_type": "STRUCT<x INT64>", "is_nullable": True},
    ]
    profileable, excluded = service._split_columns(raw)
    assert [c["column_name"] for c in profileable] == ["id"]
    assert {c.column_name for c in excluded} == {"tags", "meta"}
    assert all("STRUCT" in e.reason or "ARRAY" in e.reason for e in excluded)


def test_validate_date_column_raises_with_available_columns_when_missing():
    profileable = [
        {"column_name": "id", "data_type": "INT64"},
        {"column_name": "signup_date", "data_type": "DATE"},
    ]
    with pytest.raises(InvalidDateColumnError) as exc_info:
        service._validate_date_column("ghost_column", profileable)
    assert exc_info.value.available_columns == ["signup_date"]


def test_validate_date_column_raises_when_column_exists_but_is_not_a_date_type():
    profileable = [{"column_name": "lead_status", "data_type": "STRING"}]
    with pytest.raises(InvalidDateColumnError):
        service._validate_date_column("lead_status", profileable)


def test_validate_date_column_passes_for_valid_date_column():
    profileable = [{"column_name": "signup_date", "data_type": "DATE"}]
    service._validate_date_column("signup_date", profileable)


def test_validate_date_column_noop_when_none():
    service._validate_date_column(None, [])


# --- _infer_logical_type ----------------------------------------------------


def test_infer_logical_type_id_when_distinct_pct_above_90():
    result = service._infer_logical_type("STRING", 950, 95.0, "a", "z")
    assert result == InferredLogicalType.ID


def test_infer_logical_type_boolean_takes_priority_over_categorical():
    """distinct_count==2 também satisfaz distinct_count<50 — boolean tem
    que vencer, senão a regra nunca seria alcançável (ver docstring de
    _infer_logical_type)."""
    result = service._infer_logical_type("BOOL", 2, 0.02, False, True)
    assert result == InferredLogicalType.BOOLEAN


def test_infer_logical_type_email_when_min_or_max_contains_at():
    result = service._infer_logical_type("STRING", 800, 80.0, "a@b.com", "z@z.com")
    assert result == InferredLogicalType.EMAIL


def test_infer_logical_type_date_string_when_min_max_match_pattern():
    result = service._infer_logical_type("STRING", 800, 80.0, "2026-01-01", "2026-12-31")
    assert result == InferredLogicalType.DATE_STRING


def test_infer_logical_type_numeric_string_when_min_max_are_numeric():
    result = service._infer_logical_type("STRING", 800, 80.0, "10", "9999.5")
    assert result == InferredLogicalType.NUMERIC_STRING


def test_infer_logical_type_categorical_when_distinct_count_below_50():
    result = service._infer_logical_type("STRING", 4, 0.04, "lead", "venda_concluida")
    assert result == InferredLogicalType.CATEGORICAL


def test_infer_logical_type_free_text_for_high_cardinality_string_without_pattern():
    result = service._infer_logical_type("STRING", 900, 90.0, "some free text", "zzz other text")
    assert result == InferredLogicalType.FREE_TEXT


def test_infer_logical_type_unknown_for_high_cardinality_non_string():
    result = service._infer_logical_type("BOOL", 900, 90.0, 1.5, 9999.9)
    assert result == InferredLogicalType.UNKNOWN


def test_infer_logical_type_email_check_skipped_for_non_string_columns():
    """Uma coluna não-STRING jamais deveria virar 'email' mesmo se o valor
    stringificado contivesse '@' por acaso."""
    result = service._infer_logical_type("BOOL", 900, 90.0, "1@2", "3@4")
    assert result != InferredLogicalType.EMAIL


def test_infer_logical_type_handles_null_min_max_for_fully_null_column():
    result = service._infer_logical_type("STRING", 0, 0.0, None, None)
    assert result == InferredLogicalType.CATEGORICAL


# --- _infer_logical_type: tipo físico numérico/data (prioridade sobre cardinalidade) ---


@pytest.mark.parametrize("data_type", ["INTEGER", "INT64", "FLOAT64", "NUMERIC", "BIGNUMERIC"])
def test_infer_logical_type_numeric_for_numeric_physical_types(data_type):
    result = service._infer_logical_type(data_type, 900, 90.0, 1.5, 9999.9)
    assert result == InferredLogicalType.NUMERIC


def test_infer_logical_type_numeric_takes_priority_over_categorical():
    result = service._infer_logical_type("INT64", 4, 0.04, 1, 4)
    assert result == InferredLogicalType.NUMERIC


def test_infer_logical_type_numeric_takes_priority_over_id():
    result = service._infer_logical_type("FLOAT64", 950, 95.0, 1.5, 9999.9)
    assert result == InferredLogicalType.NUMERIC


def test_infer_logical_type_date_for_date_physical_type():
    result = service._infer_logical_type("DATE", 4, 0.04, "2026-01-01", "2026-12-31")
    assert result == InferredLogicalType.DATE


@pytest.mark.parametrize("data_type", ["DATETIME", "TIMESTAMP"])
def test_infer_logical_type_timestamp_for_datetime_and_timestamp_physical_types(data_type):
    result = service._infer_logical_type(data_type, 4, 0.04, "2026-01-01", "2026-12-31")
    assert result == InferredLogicalType.TIMESTAMP


def test_infer_logical_type_date_does_not_fall_into_categorical():
    """distinct_count baixo não pode desviar DATE/TIMESTAMP pra categorical —
    o tipo físico decide direto, sem checar cardinalidade."""
    result = service._infer_logical_type("DATE", 2, 0.02, "2026-01-01", "2026-01-02")
    assert result == InferredLogicalType.DATE
    assert result != InferredLogicalType.CATEGORICAL


# --- _coefficient_of_variation ----------------------------------------------


def test_coefficient_of_variation_none_for_non_numeric_type():
    assert service._coefficient_of_variation("STRING", 10.0, 2.0) is None


def test_coefficient_of_variation_none_when_avg_is_zero():
    assert service._coefficient_of_variation("FLOAT64", 0, 2.0) is None


def test_coefficient_of_variation_none_when_avg_or_stddev_missing():
    assert service._coefficient_of_variation("FLOAT64", None, 2.0) is None
    assert service._coefficient_of_variation("FLOAT64", 10.0, None) is None


def test_coefficient_of_variation_computes_stddev_over_avg_times_100():
    result = service._coefficient_of_variation("FLOAT64", 50.0, 5.0)
    assert result == 10.0


# --- _quality_flag -----------------------------------------------------------


def test_quality_flag_ok_at_and_above_80():
    assert service._quality_flag(80.0) == QualityFlag.OK
    assert service._quality_flag(100.0) == QualityFlag.OK


def test_quality_flag_warning_between_50_and_80():
    assert service._quality_flag(50.0) == QualityFlag.WARNING
    assert service._quality_flag(79.9) == QualityFlag.WARNING


def test_quality_flag_critical_below_50():
    assert service._quality_flag(49.9) == QualityFlag.CRITICAL
    assert service._quality_flag(0.0) == QualityFlag.CRITICAL


# --- _human_bytes / _estimate_cost_usd ---------------------------------------


def test_human_bytes_formats_small_values_in_bytes():
    assert service._human_bytes(500) == "500.00 B"


def test_human_bytes_formats_kilobytes():
    assert service._human_bytes(2_500) == "2.50 KB"


def test_human_bytes_formats_megabytes():
    assert service._human_bytes(2_500_000) == "2.50 MB"


def test_estimate_cost_usd_uses_configured_price_per_tib(monkeypatch):
    monkeypatch.setattr(service.settings, "bigquery_price_usd_per_tib", 6.25)
    one_tib = 1024**4
    assert service._estimate_cost_usd(one_tib) == 6.25


# --- estimate_profiling / run_profiling orchestration ------------------------


def test_estimate_profiling_returns_dry_run_bytes_and_cost(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "lead_status", "data_type": "STRING", "is_nullable": True}
        ],
    )
    monkeypatch.setattr(service.repository, "dry_run", lambda client, project_id, sql: 849813)

    result = service.estimate_profiling(
        client, "observability-hub-dev", "RAW", "crm_leads", ProfilingRequest()
    )

    assert result.estimated_bytes == 849813
    assert "KB" in result.estimated_bytes_human
    assert "SELECT" in result.sql


def test_estimate_profiling_omits_tablesample_for_view(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch, is_view=True)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "lead_status", "data_type": "STRING", "is_nullable": True}
        ],
    )
    monkeypatch.setattr(service.repository, "dry_run", lambda client, project_id, sql: 0)

    result = service.estimate_profiling(
        client, "observability-hub-dev", "RAW", "crm_leads_view", ProfilingRequest()
    )

    assert "TABLESAMPLE" not in result.sql


def test_estimate_profiling_raises_for_invalid_sample_percent(monkeypatch):
    client = _fake_client()
    with pytest.raises(InvalidSamplePercentError):
        service.estimate_profiling(
            client,
            "observability-hub-dev",
            "RAW",
            "crm_leads",
            ProfilingRequest(sample_percent=0.5),
        )


def test_estimate_profiling_raises_table_not_found_when_no_columns(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [],
    )

    with pytest.raises(TableNotFoundError):
        service.estimate_profiling(
            client, "observability-hub-dev", "RAW", "ghost", ProfilingRequest()
        )


def test_estimate_profiling_raises_invalid_date_column(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "lead_status", "data_type": "STRING", "is_nullable": True}
        ],
    )

    with pytest.raises(InvalidDateColumnError):
        service.estimate_profiling(
            client,
            "observability-hub-dev",
            "RAW",
            "crm_leads",
            ProfilingRequest(date_column="ghost", date_window_days=30),
        )


def _stub_columns_for_run(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "lead_status", "data_type": "STRING", "is_nullable": True},
            {"column_name": "revenue", "data_type": "FLOAT64", "is_nullable": True},
            {"column_name": "metadata", "data_type": "STRUCT<x INT64>", "is_nullable": True},
        ],
    )


def test_run_profiling_builds_full_response(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(service.history_repository, "save_run", lambda *a, **kw: None)
    _stub_columns_for_run(monkeypatch)

    main_result = {
        "_total_sampled_rows": 10000,
        "_approx_distinct_rows": 9526,
        "lead_status__count_filled": 10000,
        "lead_status__approx_distinct": 4,
        "lead_status__min": "lead",
        "lead_status__max": "venda_concluida",
        "revenue__count_filled": 10000,
        "revenue__approx_distinct": 4000,
        "revenue__min": 10.0,
        "revenue__max": 9999.99,
        "revenue__avg": 500.0,
        "revenue__stddev": 50.0,
    }
    monkeypatch.setattr(
        service.repository,
        "execute_main_query",
        lambda client, project_id, sql, timeout: main_result,
    )
    monkeypatch.setattr(
        service.repository,
        "get_total_table_rows",
        lambda client, project_id, dataset_id, table_id, location: 10000,
    )
    monkeypatch.setattr(
        service.repository,
        "execute_top_n_query",
        lambda client, project_id, sql, timeout: [
            {"value": "lead", "count": 4200},
            {"value": "qualificado", "count": 3100},
            {"value": "proposta", "count": 1800},
            {"value": "venda_concluida", "count": 900},
        ],
    )

    result = service.run_profiling(
        client,
        MagicMock(),
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        ProfilingRequest(),
        "a@dp6.com.br",
    )

    assert result.table_summary.total_sampled_rows == 10000
    assert result.table_summary.total_table_rows == 10000
    assert result.table_summary.estimated_duplicate_rows == 474
    assert result.table_summary.estimated_duplicate_pct == 4.74

    assert len(result.excluded_columns) == 1
    assert result.excluded_columns[0].column_name == "metadata"

    lead_status = next(c for c in result.columns if c.column_name == "lead_status")
    assert lead_status.completeness_pct == 100.0
    assert lead_status.distinct_count == 4
    assert lead_status.distinct_pct == 0.04
    assert lead_status.inferred_logical_type == InferredLogicalType.CATEGORICAL
    assert lead_status.quality_flag == QualityFlag.OK
    assert lead_status.coefficient_of_variation is None
    assert len(lead_status.top_values) == 4
    assert lead_status.top_values[0].pct == 42.0

    revenue = next(c for c in result.columns if c.column_name == "revenue")
    assert revenue.top_values is None  # distinct_count 4000 >= 50
    assert revenue.coefficient_of_variation == 10.0


def test_run_profiling_zero_rows_has_zeroed_metrics_without_error(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(service.history_repository, "save_run", lambda *a, **kw: None)
    _stub_columns_for_run(monkeypatch)

    main_result = {
        "_total_sampled_rows": 0,
        "_approx_distinct_rows": 0,
        "lead_status__count_filled": 0,
        "lead_status__approx_distinct": 0,
        "lead_status__min": None,
        "lead_status__max": None,
        "revenue__count_filled": 0,
        "revenue__approx_distinct": 0,
        "revenue__min": None,
        "revenue__max": None,
        "revenue__avg": None,
        "revenue__stddev": None,
    }
    monkeypatch.setattr(
        service.repository,
        "execute_main_query",
        lambda client, project_id, sql, timeout: main_result,
    )
    monkeypatch.setattr(
        service.repository,
        "get_total_table_rows",
        lambda client, project_id, dataset_id, table_id, location: 0,
    )

    result = service.run_profiling(
        client,
        MagicMock(),
        "observability-hub-dev",
        "RAW",
        "empty_table",
        ProfilingRequest(),
        "a@dp6.com.br",
    )

    assert result.table_summary.total_sampled_rows == 0
    assert result.table_summary.estimated_duplicate_pct == 0.0
    assert result.table_summary.overall_density == 0.0
    lead_status = next(c for c in result.columns if c.column_name == "lead_status")
    assert lead_status.completeness_pct == 0.0
    assert lead_status.quality_flag == QualityFlag.CRITICAL
    assert lead_status.top_values is None


def test_run_profiling_all_null_column_is_critical(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(service.history_repository, "save_run", lambda *a, **kw: None)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "middle_name", "data_type": "STRING", "is_nullable": True},
        ],
    )
    main_result = {
        "_total_sampled_rows": 1000,
        "_approx_distinct_rows": 1,
        "middle_name__count_filled": 0,
        "middle_name__approx_distinct": 0,
        "middle_name__min": None,
        "middle_name__max": None,
    }
    monkeypatch.setattr(
        service.repository,
        "execute_main_query",
        lambda client, project_id, sql, timeout: main_result,
    )
    monkeypatch.setattr(
        service.repository,
        "get_total_table_rows",
        lambda client, project_id, dataset_id, table_id, location: 1000,
    )
    monkeypatch.setattr(
        service.repository, "execute_top_n_query", lambda client, project_id, sql, timeout: []
    )

    result = service.run_profiling(
        client,
        MagicMock(),
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        ProfilingRequest(),
        "a@dp6.com.br",
    )

    col = result.columns[0]
    assert col.completeness_pct == 0.0
    assert col.null_count == 1000
    assert col.quality_flag == QualityFlag.CRITICAL


def test_run_profiling_uses_exact_distinct_alias_when_requested(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(service.history_repository, "save_run", lambda *a, **kw: None)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "lead_status", "data_type": "STRING", "is_nullable": True},
        ],
    )
    main_result = {
        "_total_sampled_rows": 100,
        "_approx_distinct_rows": 4,
        "lead_status__count_filled": 100,
        "lead_status__exact_distinct": 4,
        "lead_status__min": "lead",
        "lead_status__max": "venda",
    }
    monkeypatch.setattr(
        service.repository,
        "execute_main_query",
        lambda client, project_id, sql, timeout: main_result,
    )
    monkeypatch.setattr(
        service.repository,
        "get_total_table_rows",
        lambda client, project_id, dataset_id, table_id, location: 100,
    )
    monkeypatch.setattr(
        service.repository, "execute_top_n_query", lambda client, project_id, sql, timeout: []
    )

    result = service.run_profiling(
        client,
        MagicMock(),
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        ProfilingRequest(uniqueness_method=UniquenessMethod.EXACT),
        "a@dp6.com.br",
    )

    assert result.columns[0].distinct_count == 4


def test_run_profiling_omits_tablesample_for_view(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch, is_view=True)
    monkeypatch.setattr(service.history_repository, "save_run", lambda *a, **kw: None)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "lead_status", "data_type": "STRING", "is_nullable": True},
        ],
    )
    main_result = {
        "_total_sampled_rows": 100,
        "_approx_distinct_rows": 4,
        "lead_status__count_filled": 100,
        "lead_status__approx_distinct": 4,
        "lead_status__min": "lead",
        "lead_status__max": "venda",
    }
    captured_top_n_sql = {}

    def fake_execute_top_n_query(client, project_id, sql, timeout):
        captured_top_n_sql["sql"] = sql
        return []

    monkeypatch.setattr(
        service.repository,
        "execute_main_query",
        lambda client, project_id, sql, timeout: main_result,
    )
    monkeypatch.setattr(
        service.repository,
        "get_total_table_rows",
        lambda client, project_id, dataset_id, table_id, location: 100,
    )
    monkeypatch.setattr(service.repository, "execute_top_n_query", fake_execute_top_n_query)

    result = service.run_profiling(
        client,
        MagicMock(),
        "observability-hub-dev",
        "RAW",
        "crm_leads_view",
        ProfilingRequest(),
        "a@dp6.com.br",
    )

    assert "TABLESAMPLE" not in result.sql
    assert "TABLESAMPLE" not in captured_top_n_sql["sql"]


# --- timeout handling ---------------------------------------------------


def test_remaining_budget_raises_when_deadline_passed():
    with pytest.raises(ProfilingTimeoutError):
        service._remaining_budget(-100.0, "proj", "RAW", "leads")


def test_run_with_timeout_guard_converts_python_timeout_error():
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("deadline exceeded")

    with pytest.raises(ProfilingTimeoutError):
        service._run_with_timeout_guard("proj", "RAW", "leads", raise_timeout)


def test_run_with_timeout_guard_passes_through_result():
    result = service._run_with_timeout_guard("proj", "RAW", "leads", lambda: 42)
    assert result == 42


# --- get_null_distribution -----------------------------------------------


def test_get_null_distribution_builds_series(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "email", "data_type": "STRING", "is_nullable": True},
            {"column_name": "signup_date", "data_type": "DATE", "is_nullable": False},
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "execute_null_distribution_query",
        lambda client, project_id, sql, timeout: [
            {"period": "2026-07-01", "null_count": 0, "total_rows": 450},
            {"period": "2026-07-02", "null_count": 12, "total_rows": 430},
        ],
    )

    result = service.get_null_distribution(
        client,
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        "email",
        "signup_date",
        30,
        Granularity.DAY,
    )

    assert result.column_name == "email"
    assert len(result.series) == 2
    assert result.series[1].null_pct == round(12 / 430 * 100, 2)


def test_get_null_distribution_raises_invalid_date_column(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "email", "data_type": "STRING", "is_nullable": True},
        ],
    )

    with pytest.raises(InvalidDateColumnError):
        service.get_null_distribution(
            client,
            "observability-hub-dev",
            "RAW",
            "crm_leads",
            "email",
            "ghost_date",
            30,
            Granularity.DAY,
        )


def test_get_null_distribution_handles_zero_total_rows_period(monkeypatch):
    client = _fake_client()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "email", "data_type": "STRING", "is_nullable": True},
            {"column_name": "signup_date", "data_type": "DATE", "is_nullable": False},
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "execute_null_distribution_query",
        lambda client, project_id, sql, timeout: [
            {"period": "2026-07-01", "null_count": 0, "total_rows": 0},
        ],
    )

    result = service.get_null_distribution(
        client,
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        "email",
        "signup_date",
        30,
        Granularity.DAY,
    )

    assert result.series[0].null_pct == 0.0


# --- run_profiling salva no histórico ---------------------------------------


def test_run_profiling_saves_run_to_history(monkeypatch):
    client = _fake_client()
    firestore_client = MagicMock()
    _stub_region_resolution(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_table_columns",
        lambda client, project_id, dataset_id, table_id, location: [
            {"column_name": "email", "data_type": "STRING", "is_nullable": True},
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "execute_main_query",
        lambda client, project_id, sql, budget: {
            "_total_sampled_rows": 10,
            "_approx_distinct_rows": 10,
            "email__count_filled": 10,
            "email__approx_distinct": 10,
            "email__min": "a@dp6.com.br",
            "email__max": "z@dp6.com.br",
        },
    )
    monkeypatch.setattr(
        service.repository,
        "get_total_table_rows",
        lambda client, project_id, dataset_id, table_id, location: 10,
    )
    monkeypatch.setattr(
        service.repository, "execute_top_n_query", lambda client, project_id, sql, timeout: []
    )
    save_calls = []
    monkeypatch.setattr(
        service.history_repository,
        "save_run",
        lambda *args, **kwargs: save_calls.append((args, kwargs)),
    )

    service.run_profiling(
        client,
        firestore_client,
        "observability-hub-dev",
        "RAW",
        "crm_leads",
        ProfilingRequest(),
        "a@dp6.com.br",
    )

    assert len(save_calls) == 1
    args, kwargs = save_calls[0]
    assert args[0] is firestore_client
    assert args[1:4] == ("observability-hub-dev", "RAW", "crm_leads")
    assert kwargs["executed_by"] == "a@dp6.com.br"
    assert kwargs["overall_density"] == 100.0
    assert kwargs["estimated_duplicate_pct"] == 0.0
    assert kwargs["columns"] == [
        {"column_name": "email", "completeness_pct": 100.0, "quality_flag": "ok"}
    ]


# --- get_quality_history -----------------------------------------------------


def test_get_quality_history_returns_empty_when_never_profiled(monkeypatch):
    firestore_client = MagicMock()
    monkeypatch.setattr(service.history_repository, "list_runs", lambda *a, **kw: [])

    result = service.get_quality_history(
        firestore_client, "observability-hub-dev", "RAW", "crm_leads"
    )

    assert result.runs == []
    assert result.project_id == "observability-hub-dev"
    assert result.dataset_id == "RAW"
    assert result.table_id == "crm_leads"


def test_get_quality_history_maps_raw_runs_to_response(monkeypatch):
    firestore_client = MagicMock()
    executed_at = datetime(2026, 8, 10, tzinfo=UTC)
    monkeypatch.setattr(
        service.history_repository,
        "list_runs",
        lambda *a, **kw: [
            {
                "executed_at": executed_at,
                "executed_by": "a@dp6.com.br",
                "overall_density": 91.3,
                "estimated_duplicate_pct": 1.5,
                "columns": [
                    {"column_name": "email", "completeness_pct": 91.3, "quality_flag": "ok"}
                ],
            }
        ],
    )

    result = service.get_quality_history(
        firestore_client, "observability-hub-dev", "RAW", "crm_leads"
    )

    assert len(result.runs) == 1
    run = result.runs[0]
    assert run.executed_at == executed_at
    assert run.executed_by == "a@dp6.com.br"
    assert run.overall_density == 91.3
    assert run.estimated_duplicate_pct == 1.5
    assert run.columns[0].column_name == "email"
    assert run.columns[0].quality_flag == QualityFlag.OK
