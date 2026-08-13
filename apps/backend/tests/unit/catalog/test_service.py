from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import (
    DatasetNotFoundError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    TableNotFoundError,
    TableNotPartitionedError,
)
from observability_hub.domains.catalog import service


def _fake_client(project: str = "observability-hub-dev") -> MagicMock:
    client = MagicMock(name="bigquery.Client")
    client.project = project
    return client


def test_validate_project_happy_path(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "get_datasets_summary",
        lambda client, project_id, regions: [{"dataset_id": "RAW"}, {"dataset_id": "OTHER"}],
    )

    result = service.validate_project(client, "observability-hub-dev")

    assert result.accessible is True
    assert result.available_regions == ["US"]
    assert result.total_datasets == 2


def test_validate_project_empty_project_has_zero_datasets(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: [])
    monkeypatch.setattr(
        service.repository, "get_datasets_summary", lambda client, project_id, regions: []
    )

    result = service.validate_project(client, "empty-project")

    assert result.accessible is True
    assert result.available_regions == []
    assert result.total_datasets == 0


def test_validate_project_is_native_true_when_project_id_matches_runtime_project(monkeypatch):
    client = _fake_client(project="observability-hub-dev")
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "get_datasets_summary", lambda client, project_id, regions: []
    )

    result = service.validate_project(client, "observability-hub-dev")

    assert result.is_native is True


def test_validate_project_is_native_false_for_external_project(monkeypatch):
    client = _fake_client(project="observability-hub-dev")
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "get_datasets_summary", lambda client, project_id, regions: []
    )

    result = service.validate_project(client, "some-customer-project")

    assert result.is_native is False


def test_validate_project_propagates_access_denied(monkeypatch):
    client = _fake_client()

    def raise_denied(project_id, client):
        raise ProjectAccessDeniedError(project_id)

    monkeypatch.setattr(service, "discover_regions", raise_denied)

    with pytest.raises(ProjectAccessDeniedError):
        service.validate_project(client, "some-project")


def test_validate_project_propagates_not_found(monkeypatch):
    client = _fake_client()

    def raise_not_found(project_id, client):
        raise ProjectNotFoundError(project_id)

    monkeypatch.setattr(service, "discover_regions", raise_not_found)

    with pytest.raises(ProjectNotFoundError):
        service.validate_project(client, "ghost-project")


def test_list_datasets_builds_response(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    raw = [
        {
            "dataset_id": "RAW",
            "location": "US",
            "creation_time": "2026-06-03T19:40:00Z",
            "last_modified_time": "2026-06-08T18:38:00Z",
            "total_tables": 3,
            "total_views": 0,
            "total_size_bytes": 2075443,
            "total_size_gb": 0.002,
            "total_rows": 30000,
        }
    ]
    monkeypatch.setattr(
        service.repository, "get_datasets_summary", lambda client, project_id, regions: raw
    )

    result = service.list_datasets(client, "observability-hub-dev")

    assert result.total_datasets == 1
    assert result.regions_found == ["US"]
    assert result.datasets[0].dataset_id == "RAW"


def test_list_tables_resolves_region_and_builds_response(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    raw = [
        {
            "table_id": "ga4_events",
            "table_type": "TABLE",
            "creation_time": "2026-06-08T18:38:40Z",
            "last_modified_time": "2026-06-08T18:38:40Z",
            "size_bytes": 576920,
            "size_gb": 0.0005,
            "row_count": 10000,
            "column_count": 8,
            "is_partitioned": False,
            "partition_column": None,
            "is_clustered": False,
            "clustering_columns": [],
            "location": "US",
        }
    ]
    monkeypatch.setattr(
        service.repository,
        "get_tables_summary",
        lambda client, project_id, dataset_id, location, table_type=None: raw,
    )

    result = service.list_tables(client, "observability-hub-dev", "RAW")

    assert result.location == "US"
    assert result.total_tables == 1
    assert result.tables[0].table_id == "ga4_events"


def test_list_tables_fills_partition_stats_only_for_partitioned_tables(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "us-central1",
    )
    raw = [
        {
            "table_id": "events",
            "table_type": "TABLE",
            "creation_time": "2026-06-08T18:38:40Z",
            "last_modified_time": "2026-06-08T18:38:40Z",
            "size_bytes": 576920,
            "size_gb": 0.0005,
            "row_count": 10000,
            "column_count": 8,
            "is_partitioned": True,
            "partition_column": "event_date",
            "is_clustered": False,
            "clustering_columns": [],
            "location": "us-central1",
        },
        {
            "table_id": "dim_users",
            "table_type": "TABLE",
            "creation_time": "2026-06-08T18:38:40Z",
            "last_modified_time": "2026-06-08T18:38:40Z",
            "size_bytes": 1000,
            "size_gb": 0.0001,
            "row_count": 10,
            "column_count": 3,
            "is_partitioned": False,
            "partition_column": None,
            "is_clustered": False,
            "clustering_columns": [],
            "location": "us-central1",
        },
    ]
    monkeypatch.setattr(
        service.repository,
        "get_tables_summary",
        lambda client, project_id, dataset_id, location, table_type=None: raw,
    )
    calls = []

    def fake_get_partition_stats(client, project_id, dataset_id, table_id, partition_field):
        calls.append((table_id, partition_field))
        return {"min_partition": "20260101", "max_partition": "20260812", "partition_count": 224}

    monkeypatch.setattr(service.repository, "get_partition_stats", fake_get_partition_stats)

    result = service.list_tables(client, "observability-hub-dev", "RAW")

    assert calls == [("events", "event_date")]
    events = next(t for t in result.tables if t.table_id == "events")
    dim_users = next(t for t in result.tables if t.table_id == "dim_users")
    assert events.min_partition == "20260101"
    assert events.partition_count == 224
    assert dim_users.min_partition is None
    assert dim_users.partition_count is None


def test_list_tables_propagates_dataset_not_found(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])

    def raise_not_found(client, project_id, dataset_id, candidate_regions):
        raise DatasetNotFoundError(project_id, dataset_id)

    monkeypatch.setattr(service.repository, "resolve_dataset_region", raise_not_found)

    with pytest.raises(DatasetNotFoundError):
        service.list_tables(client, "observability-hub-dev", "GHOST")


def test_get_table_detail_builds_response(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    raw_detail = {
        "table_id": "ga4_events",
        "table_type": "TABLE",
        "creation_time": "2026-06-08T18:38:40Z",
        "last_modified_time": "2026-06-08T18:38:40Z",
        "size_bytes": 576920,
        "size_gb": 0.0005,
        "row_count": 10000,
        "column_count": 1,
        "is_partitioned": False,
        "partition_column": None,
        "is_clustered": False,
        "clustering_columns": [],
        "location": "US",
        "columns": [
            {
                "column_name": "event_date",
                "data_type": "STRING",
                "is_nullable": True,
                "description": None,
            }
        ],
        "labels": {},
        "description": None,
    }
    monkeypatch.setattr(
        service.repository,
        "get_table_detail",
        lambda client, project_id, dataset_id, table_id, location: dict(raw_detail),
    )

    result = service.get_table_detail(client, "observability-hub-dev", "RAW", "ga4_events")

    assert result.table_id == "ga4_events"
    assert len(result.columns) == 1
    assert result.columns[0].column_name == "event_date"


def test_get_table_detail_propagates_table_not_found(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )

    def raise_not_found(client, project_id, dataset_id, table_id, location):
        raise TableNotFoundError(project_id, dataset_id, table_id)

    monkeypatch.setattr(service.repository, "get_table_detail", raise_not_found)

    with pytest.raises(TableNotFoundError):
        service.get_table_detail(client, "observability-hub-dev", "RAW", "ghost")


def _tables_summary_stub(tables):
    def fake(client, project_id, dataset_id, location, table_type=None):
        return tables

    return fake


def test_get_table_partitions_builds_response(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    monkeypatch.setattr(
        service.repository,
        "get_tables_summary",
        _tables_summary_stub(
            [
                {
                    "table_id": "events",
                    "is_partitioned": True,
                    "partition_column": "event_date",
                    "partition_type": "event_date (DAY)",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        service.repository,
        "get_table_partitions",
        lambda client, project_id, dataset_id, table_id, partition_field: [
            {"value": "2026-08-12", "row_count": 1800},
            {"value": "2026-08-11", "row_count": 1500},
        ],
    )

    result = service.get_table_partitions(client, "observability-hub-dev", "RAW", "events")

    assert result.partition_column == "event_date"
    assert result.partition_type == "event_date (DAY)"
    assert result.total_partitions == 2
    assert result.partitions[0].value == "2026-08-12"


def test_get_table_partitions_raises_when_table_missing(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    monkeypatch.setattr(service.repository, "get_tables_summary", _tables_summary_stub([]))

    with pytest.raises(TableNotFoundError):
        service.get_table_partitions(client, "observability-hub-dev", "RAW", "ghost")


def test_get_table_partitions_raises_when_table_not_partitioned(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    monkeypatch.setattr(
        service.repository,
        "get_tables_summary",
        _tables_summary_stub(
            [
                {
                    "table_id": "dim_users",
                    "is_partitioned": False,
                    "partition_column": None,
                    "partition_type": None,
                }
            ]
        ),
    )

    with pytest.raises(TableNotPartitionedError):
        service.get_table_partitions(client, "observability-hub-dev", "RAW", "dim_users")


def test_search_tables_builds_response_with_match_and_prefix_without_match(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "search_tables",
        lambda client, project_id, regions, query, mode: [
            {"dataset_id": "analytics_123", "table_id": "events_20260812", "table_type": "TABLE"}
        ],
    )
    monkeypatch.setattr(
        service,
        "get_tables_metadata",
        lambda client, table_refs: {
            "observability-hub-dev.analytics_123.events_20260812": SimpleNamespace(
                modified="2026-08-12T03:00:00Z", num_rows=22096
            )
        },
    )
    monkeypatch.setattr(service.repository, "derive_search_prefix", lambda query: "events_")
    monkeypatch.setattr(
        service.repository,
        "search_tables_by_prefix",
        lambda client, project_id, regions, prefix, exclude_dataset_ids: [
            {"dataset_id": "analytics_456", "latest_table": "events_20260810"},
        ],
    )

    result = service.search_tables(client, "observability-hub-dev", "events_20260812", "exact")

    assert result.query == "events_20260812"
    assert result.mode == "exact"
    assert len(result.datasets_with_match) == 1
    assert result.datasets_with_match[0].dataset_id == "analytics_123"
    assert (
        result.datasets_with_match[0].last_modified_time.isoformat() == "2026-08-12T03:00:00+00:00"
    )
    assert result.datasets_with_match[0].row_count == 22096
    assert len(result.datasets_without_match) == 1
    assert result.datasets_without_match[0].dataset_id == "analytics_456"
    assert result.datasets_without_match[0].reason == "prefix_exists"
    assert result.datasets_without_match[0].latest_partition == "events_20260810"


def test_search_tables_skips_prefix_search_when_query_has_no_trailing_digits(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "search_tables",
        lambda client, project_id, regions, query, mode: [],
    )
    monkeypatch.setattr(service, "get_tables_metadata", lambda client, table_refs: {})
    calls = []
    monkeypatch.setattr(
        service.repository,
        "search_tables_by_prefix",
        lambda *a, **k: calls.append(1) or [],
    )

    result = service.search_tables(client, "observability-hub-dev", "ga4_events", "exact")

    assert result.datasets_with_match == []
    assert result.datasets_without_match == []
    assert calls == []


def test_search_tables_no_matches_returns_empty_lists(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "search_tables",
        lambda client, project_id, regions, query, mode: [],
    )
    monkeypatch.setattr(service, "get_tables_metadata", lambda client, table_refs: {})
    monkeypatch.setattr(
        service.repository,
        "search_tables_by_prefix",
        lambda client, project_id, regions, prefix, exclude_dataset_ids: [],
    )

    result = service.search_tables(client, "observability-hub-dev", "events_99999999", "contains")

    assert result.datasets_with_match == []
    assert result.datasets_without_match == []


def test_search_tables_not_contains_lists_datasets_with_zero_matching_tables(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "get_datasets_summary",
        lambda client, project_id, regions: [
            {"dataset_id": "RAW"},
            {"dataset_id": "TRUSTED"},
            {"dataset_id": "analytics_100001"},
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "search_tables",
        lambda client, project_id, regions, query, mode: [
            {"dataset_id": "analytics_100001", "table_id": "crm_leads", "table_type": "TABLE"}
        ],
    )

    result = service.search_tables(client, "observability-hub-dev", "crm", "not_contains")

    assert result.mode == "not_contains"
    assert result.datasets_with_match == []
    assert {d.dataset_id for d in result.datasets_without_match} == {"RAW", "TRUSTED"}
    assert all(d.reason == "no_match" for d in result.datasets_without_match)


def test_search_tables_not_contains_does_not_run_prefix_search(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "get_datasets_summary", lambda client, project_id, regions: []
    )
    monkeypatch.setattr(
        service.repository,
        "search_tables",
        lambda client, project_id, regions, query, mode: [],
    )
    calls = []
    monkeypatch.setattr(
        service.repository,
        "search_tables_by_prefix",
        lambda *a, **k: calls.append(1) or [],
    )

    service.search_tables(client, "observability-hub-dev", "events_20260812", "not_contains")

    assert calls == []
