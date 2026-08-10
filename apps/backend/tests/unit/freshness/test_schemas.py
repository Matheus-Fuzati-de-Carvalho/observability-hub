from observability_hub.domains.freshness.schemas import (
    DatasetFreshnessSummary,
    FreshnessCounts,
    FreshnessDatasetResponse,
    FreshnessProjectResponse,
    SLAStatus,
    TableFreshness,
)


def test_dataset_freshness_summary_matches_spec_example():
    payload = {
        "dataset_id": "RAW",
        "location": "US",
        "total_tables": 3,
        "ok": 0,
        "warning_12_24": 0,
        "warning_24_48": 0,
        "warning_48_7d": 0,
        "warning_7d_1m": 0,
        "stale": 3,
        "worst_status": "stale",
    }
    model = DatasetFreshnessSummary(**payload)
    assert model.worst_status == SLAStatus.STALE


def test_freshness_project_response_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "evaluated_at": "2026-08-05T10:00:00Z",
        "datasets": [
            {
                "dataset_id": "RAW",
                "location": "US",
                "total_tables": 3,
                "ok": 0,
                "warning_12_24": 0,
                "warning_24_48": 0,
                "warning_48_7d": 0,
                "warning_7d_1m": 0,
                "stale": 3,
                "worst_status": "stale",
            }
        ],
    }
    model = FreshnessProjectResponse(**payload)
    assert len(model.datasets) == 1


def test_dataset_freshness_summary_allows_null_worst_status_for_empty_dataset():
    payload = {
        "dataset_id": "EMPTY",
        "location": "US",
        "total_tables": 0,
        "ok": 0,
        "warning_12_24": 0,
        "warning_24_48": 0,
        "warning_48_7d": 0,
        "warning_7d_1m": 0,
        "stale": 0,
        "worst_status": None,
    }
    model = DatasetFreshnessSummary(**payload)
    assert model.worst_status is None


def test_table_freshness_matches_spec_example():
    payload = {
        "table_id": "crm_leads",
        "table_type": "TABLE",
        "last_modified_time": "2024-01-15T00:00:00Z",
        "hours_since_update": 14424.0,
        "sla_status": "stale",
        "size_bytes": 849813,
        "row_count": 10000,
    }
    model = TableFreshness(**payload)
    assert model.sla_status == SLAStatus.STALE
    assert model.hours_since_update == 14424.0


def test_table_freshness_allows_null_fields_when_storage_metadata_missing():
    payload = {
        "table_id": "brand_new_table",
        "table_type": "TABLE",
        "last_modified_time": None,
        "hours_since_update": None,
        "sla_status": None,
        "size_bytes": None,
        "row_count": None,
    }
    model = TableFreshness(**payload)
    assert model.last_modified_time is None
    assert model.sla_status is None


def test_freshness_dataset_response_matches_spec_example():
    payload = {
        "project_id": "observability-hub-dev",
        "dataset_id": "RAW",
        "location": "US",
        "evaluated_at": "2026-08-05T10:00:00Z",
        "summary": {
            "total_tables": 3,
            "ok": 0,
            "warning_12_24": 0,
            "warning_24_48": 0,
            "warning_48_7d": 0,
            "warning_7d_1m": 0,
            "stale": 3,
        },
        "tables": [
            {
                "table_id": "crm_leads",
                "table_type": "TABLE",
                "last_modified_time": "2024-01-15T00:00:00Z",
                "hours_since_update": 14424.0,
                "sla_status": "stale",
                "size_bytes": 849813,
                "row_count": 10000,
            }
        ],
    }
    model = FreshnessDatasetResponse(**payload)
    assert model.summary.total_tables == 3
    assert len(model.tables) == 1


def test_freshness_counts_matches_spec_example():
    payload = {
        "total_tables": 3,
        "ok": 0,
        "warning_12_24": 0,
        "warning_24_48": 0,
        "warning_48_7d": 0,
        "warning_7d_1m": 0,
        "stale": 3,
    }
    model = FreshnessCounts(**payload)
    assert model.total_tables == 3


def test_sla_status_enum_values():
    assert SLAStatus.OK.value == "ok"
    assert SLAStatus.STALE.value == "stale"
    assert {s.value for s in SLAStatus} == {
        "ok",
        "warning_12_24",
        "warning_24_48",
        "warning_48_7d",
        "warning_7d_1m",
        "stale",
    }
