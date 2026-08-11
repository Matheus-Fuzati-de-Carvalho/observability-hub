from observability_hub.domains.quality.schemas import (
    ColumnProfile,
    EstimateResponse,
    ExcludedColumn,
    Granularity,
    InferredLogicalType,
    NullDistributionResponse,
    ProfilingRequest,
    ProfilingRunResponse,
    QualityFlag,
    TableProfilingSummary,
    TopValue,
    UniquenessMethod,
)


def test_profiling_request_matches_spec_example():
    payload = {
        "sample_percent": 10,
        "uniqueness_method": "approx",
        "date_column": "date",
        "date_window_days": 365,
    }
    model = ProfilingRequest(**payload)
    assert model.uniqueness_method == UniquenessMethod.APPROX


def test_profiling_request_defaults_match_spec_table():
    model = ProfilingRequest()
    assert model.sample_percent == 100
    assert model.uniqueness_method == UniquenessMethod.APPROX
    assert model.date_column is None
    assert model.date_window_days is None


def test_estimate_response_matches_spec_example():
    payload = {
        "estimated_bytes": 849813,
        "estimated_bytes_human": "830.13 KB",
        "estimated_cost_usd": 0.000005,
        "sql": "SELECT COUNT(*) AS _total_sampled_rows, ...",
    }
    model = EstimateResponse(**payload)
    assert model.estimated_bytes == 849813


def test_top_value_matches_spec_example():
    payload = {"value": "lead", "count": 4200, "pct": 42.0}
    model = TopValue(**payload)
    assert model.value == "lead"


def test_top_value_accepts_numeric_and_null_values():
    assert TopValue(value=42, count=1, pct=1.0).value == 42
    assert TopValue(value=3.14, count=1, pct=1.0).value == 3.14
    assert TopValue(value=None, count=1, pct=1.0).value is None


def test_column_profile_matches_spec_example():
    payload = {
        "column_name": "lead_status",
        "data_type": "STRING",
        "is_nullable": True,
        "completeness_pct": 100.0,
        "null_count": 0,
        "distinct_count": 4,
        "distinct_pct": 0.04,
        "min_value": "lead",
        "max_value": "venda_concluida",
        "top_values": [
            {"value": "lead", "count": 4200, "pct": 42.0},
            {"value": "qualificado", "count": 3100, "pct": 31.0},
        ],
        "inferred_logical_type": "categorical",
        "coefficient_of_variation": None,
        "quality_flag": "ok",
    }
    model = ColumnProfile(**payload)
    assert model.inferred_logical_type == InferredLogicalType.CATEGORICAL
    assert model.quality_flag == QualityFlag.OK
    assert len(model.top_values) == 2


def test_column_profile_allows_null_top_values_and_coefficient_of_variation():
    payload = {
        "column_name": "revenue",
        "data_type": "FLOAT64",
        "is_nullable": True,
        "completeness_pct": 40.0,
        "null_count": 600,
        "distinct_count": 400,
        "distinct_pct": 40.0,
        "min_value": 10.0,
        "max_value": 9999.99,
        "top_values": None,
        "inferred_logical_type": "unknown",
        "coefficient_of_variation": 12.5,
        "quality_flag": "critical",
    }
    model = ColumnProfile(**payload)
    assert model.top_values is None
    assert model.quality_flag == QualityFlag.CRITICAL


def test_table_profiling_summary_matches_spec_example():
    payload = {
        "total_sampled_rows": 10000,
        "total_table_rows": 10000,
        "estimated_duplicate_rows": 474,
        "estimated_duplicate_pct": 4.74,
        "overall_density": 100.0,
    }
    model = TableProfilingSummary(**payload)
    assert model.total_sampled_rows == 10000


def test_excluded_column_shape():
    model = ExcludedColumn(column_name="metadata", reason="Tipo STRUCT<x INT64> não suportado.")
    assert model.column_name == "metadata"


def test_profiling_run_response_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "dataset_id": "RAW",
        "table_id": "crm_leads",
        "executed_at": "2026-08-05T10:00:00Z",
        "parameters": {
            "sample_percent": 10,
            "uniqueness_method": "approx",
            "date_column": "date",
            "date_window_days": 365,
        },
        "sql": "...",
        "table_summary": {
            "total_sampled_rows": 10000,
            "total_table_rows": 10000,
            "estimated_duplicate_rows": 474,
            "estimated_duplicate_pct": 4.74,
            "overall_density": 100.0,
        },
        "columns": [
            {
                "column_name": "lead_status",
                "data_type": "STRING",
                "is_nullable": True,
                "completeness_pct": 100.0,
                "null_count": 0,
                "distinct_count": 4,
                "distinct_pct": 0.04,
                "min_value": "lead",
                "max_value": "venda_concluida",
                "top_values": [{"value": "lead", "count": 4200, "pct": 42.0}],
                "inferred_logical_type": "categorical",
                "coefficient_of_variation": None,
                "quality_flag": "ok",
            }
        ],
        "excluded_columns": [],
    }
    model = ProfilingRunResponse(**payload)
    assert len(model.columns) == 1
    assert model.excluded_columns == []


def test_null_distribution_response_matches_spec_example():
    payload = {
        "column_name": "email",
        "date_column": "date",
        "granularity": "day",
        "series": [
            {"period": "2026-07-01", "null_count": 0, "null_pct": 0.0, "total_rows": 450},
            {"period": "2026-07-02", "null_count": 12, "null_pct": 2.8, "total_rows": 430},
        ],
    }
    model = NullDistributionResponse(**payload)
    assert model.granularity == Granularity.DAY
    assert len(model.series) == 2


def test_uniqueness_method_enum_values():
    assert {m.value for m in UniquenessMethod} == {"approx", "exact"}


def test_inferred_logical_type_enum_values():
    assert {t.value for t in InferredLogicalType} == {
        "id",
        "categorical",
        "email",
        "date_string",
        "numeric_string",
        "boolean",
        "free_text",
        "numeric",
        "date",
        "timestamp",
        "unknown",
    }


def test_quality_flag_enum_values():
    assert {f.value for f in QualityFlag} == {"ok", "warning", "critical"}


def test_granularity_enum_values():
    assert {g.value for g in Granularity} == {"day", "week", "month"}
