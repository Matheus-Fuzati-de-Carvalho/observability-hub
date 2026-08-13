from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.favorites import service


def test_list_favorites_builds_response(monkeypatch):
    client = MagicMock()
    raw = [
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "added_at": datetime(2026, 8, 12, tzinfo=UTC),
        }
    ]
    monkeypatch.setattr(service.repository, "list_favorites", lambda client, email: raw)

    result = service.list_favorites(client, "a@dp6.com.br")

    assert len(result.favorites) == 1
    assert result.favorites[0].table_id == "events"


def test_add_favorite_builds_response(monkeypatch):
    client = MagicMock()
    raw = {
        "project_id": "proj",
        "dataset_id": "RAW",
        "table_id": "events",
        "added_at": datetime(2026, 8, 12, tzinfo=UTC),
    }
    captured = {}

    def fake_add(client, email, project_id, dataset_id, table_id):
        captured.update(
            email=email, project_id=project_id, dataset_id=dataset_id, table_id=table_id
        )
        return raw

    monkeypatch.setattr(service.repository, "add_favorite", fake_add)

    result = service.add_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    assert result.table_id == "events"
    assert captured == {
        "email": "a@dp6.com.br",
        "project_id": "proj",
        "dataset_id": "RAW",
        "table_id": "events",
    }


def test_remove_favorite_delegates_to_repository(monkeypatch):
    client = MagicMock()
    captured = {}

    def fake_remove(client, email, project_id, dataset_id, table_id):
        captured.update(
            email=email, project_id=project_id, dataset_id=dataset_id, table_id=table_id
        )

    monkeypatch.setattr(service.repository, "remove_favorite", fake_remove)

    service.remove_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    assert captured == {
        "email": "a@dp6.com.br",
        "project_id": "proj",
        "dataset_id": "RAW",
        "table_id": "events",
    }
