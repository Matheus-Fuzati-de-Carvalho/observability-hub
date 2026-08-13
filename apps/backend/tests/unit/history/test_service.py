from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.history import service


def test_get_history_builds_response(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        service.repository,
        "list_recent_table_views",
        lambda client, email: [
            {
                "project_id": "proj",
                "dataset_id": "RAW",
                "table_id": "events",
                "viewed_at": datetime(2026, 8, 12, tzinfo=UTC),
            }
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "list_recent_searches",
        lambda client, email: [
            {
                "query": "events_20260812",
                "mode": "exact",
                "project_id": "proj",
                "searched_at": datetime(2026, 8, 12, tzinfo=UTC),
            }
        ],
    )

    result = service.get_history(client, "a@dp6.com.br")

    assert len(result.recent_tables) == 1
    assert result.recent_tables[0].table_id == "events"
    assert len(result.recent_searches) == 1
    assert result.recent_searches[0].query == "events_20260812"


def test_record_table_view_delegates_to_repository(monkeypatch):
    client = MagicMock()
    captured = {}

    def fake_add(client, email, project_id, dataset_id, table_id):
        captured.update(
            email=email, project_id=project_id, dataset_id=dataset_id, table_id=table_id
        )

    monkeypatch.setattr(service.repository, "add_table_view", fake_add)

    service.record_table_view(client, "a@dp6.com.br", "proj", "RAW", "events")

    assert captured == {
        "email": "a@dp6.com.br",
        "project_id": "proj",
        "dataset_id": "RAW",
        "table_id": "events",
    }


def test_record_search_delegates_to_repository(monkeypatch):
    client = MagicMock()
    captured = {}

    def fake_add(client, email, query, mode, project_id):
        captured.update(email=email, query=query, mode=mode, project_id=project_id)

    monkeypatch.setattr(service.repository, "add_search", fake_add)

    service.record_search(client, "a@dp6.com.br", "events_20260812", "exact", "proj")

    assert captured == {
        "email": "a@dp6.com.br",
        "query": "events_20260812",
        "mode": "exact",
        "project_id": "proj",
    }
