from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import DatasetNotFoundError
from observability_hub.domains.freshness import service
from observability_hub.domains.freshness.schemas import SLAStatus


def _fake_client() -> MagicMock:
    return MagicMock(name="bigquery.Client")


def test_get_project_freshness_computes_worst_status(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    raw = [
        {
            "dataset_id": "RAW",
            "location": "US",
            "total_tables": 3,
            "ok": 0,
            "warning_12_24": 0,
            "warning_24_48": 1,
            "warning_48_7d": 0,
            "warning_7d_1m": 0,
            "stale": 2,
        }
    ]
    monkeypatch.setattr(
        service.repository,
        "get_freshness_summary_by_dataset",
        lambda client, project_id, regions: raw,
    )

    result = service.get_project_freshness(client, "observability-hub-dev")

    assert len(result.datasets) == 1
    assert result.datasets[0].worst_status == SLAStatus.STALE


def test_get_project_freshness_worst_status_is_none_for_empty_dataset(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    raw = [
        {
            "dataset_id": "EMPTY",
            "location": "US",
            "total_tables": 0,
            "ok": 0,
            "warning_12_24": 0,
            "warning_24_48": 0,
            "warning_48_7d": 0,
            "warning_7d_1m": 0,
            "stale": 0,
        }
    ]
    monkeypatch.setattr(
        service.repository,
        "get_freshness_summary_by_dataset",
        lambda client, project_id, regions: raw,
    )

    result = service.get_project_freshness(client, "observability-hub-dev")

    assert result.datasets[0].worst_status is None


def test_get_project_freshness_worst_status_picks_highest_severity_present(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    raw = [
        {
            "dataset_id": "MIXED",
            "location": "US",
            "total_tables": 2,
            "ok": 1,
            "warning_12_24": 1,
            "warning_24_48": 0,
            "warning_48_7d": 0,
            "warning_7d_1m": 0,
            "stale": 0,
        }
    ]
    monkeypatch.setattr(
        service.repository,
        "get_freshness_summary_by_dataset",
        lambda client, project_id, regions: raw,
    )

    result = service.get_project_freshness(client, "observability-hub-dev")

    assert result.datasets[0].worst_status == SLAStatus.WARNING_12_24


def test_get_dataset_freshness_resolves_region_and_builds_summary(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    raw_tables = [
        {
            "table_id": "crm_leads",
            "table_type": "TABLE",
            "last_modified_time": "2024-01-15T00:00:00Z",
            "hours_since_update": 14424.0,
            "sla_status": "stale",
            "size_bytes": 849813,
            "row_count": 10000,
        },
        {
            "table_id": "ga4_events",
            "table_type": "TABLE",
            "last_modified_time": "2026-08-10T09:00:00Z",
            "hours_since_update": 1.0,
            "sla_status": "ok",
            "size_bytes": 576920,
            "row_count": 5000,
        },
    ]
    monkeypatch.setattr(
        service.repository,
        "get_table_freshness",
        lambda client, project_id, dataset_id, location: raw_tables,
    )

    result = service.get_dataset_freshness(client, "observability-hub-dev", "RAW")

    assert result.location == "US"
    assert result.summary.total_tables == 2
    assert result.summary.stale == 1
    assert result.summary.ok == 1
    assert len(result.tables) == 2


def test_get_dataset_freshness_summary_ignores_null_sla_status(monkeypatch):
    """Tabela recém-criada sem storage_last_modified_time ainda propagado:
    entra em total_tables, mas não conta pra nenhum bucket de status."""
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    raw_tables = [
        {
            "table_id": "brand_new",
            "table_type": "TABLE",
            "last_modified_time": None,
            "hours_since_update": None,
            "sla_status": None,
            "size_bytes": None,
            "row_count": None,
        }
    ]
    monkeypatch.setattr(
        service.repository,
        "get_table_freshness",
        lambda client, project_id, dataset_id, location: raw_tables,
    )

    result = service.get_dataset_freshness(client, "observability-hub-dev", "RAW")

    assert result.summary.total_tables == 1
    assert result.summary.ok == 0
    assert result.summary.stale == 0
    assert result.tables[0].sla_status is None


def test_get_dataset_freshness_empty_dataset_has_zeroed_summary(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service,
        "resolve_dataset_region",
        lambda client, project_id, dataset_id, candidate_regions: "US",
    )
    monkeypatch.setattr(
        service.repository,
        "get_table_freshness",
        lambda client, project_id, dataset_id, location: [],
    )

    result = service.get_dataset_freshness(client, "observability-hub-dev", "EMPTY")

    assert result.summary.total_tables == 0
    assert result.tables == []


def test_get_dataset_freshness_propagates_dataset_not_found(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])

    def raise_not_found(client, project_id, dataset_id, candidate_regions):
        raise DatasetNotFoundError(project_id, dataset_id)

    monkeypatch.setattr(service, "resolve_dataset_region", raise_not_found)

    with pytest.raises(DatasetNotFoundError):
        service.get_dataset_freshness(client, "observability-hub-dev", "GHOST")
