from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import (
    DatasetNotFoundError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    TableNotFoundError,
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
