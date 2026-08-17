from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.admin import analytics_repository as repository


def _fake_client_with_collection():
    client = MagicMock()
    collection = MagicMock()
    client.collection.return_value = collection
    return client, collection


def _doc(data: dict, owner_email: str | None = None) -> MagicMock:
    snapshot = MagicMock()
    snapshot.to_dict.return_value = data
    if owner_email is not None:
        snapshot.reference.parent.parent.id = owner_email
    return snapshot


def test_record_login_adds_doc_with_email_and_timestamp():
    client, collection = _fake_client_with_collection()
    now = datetime(2026, 8, 17, tzinfo=UTC)

    repository.record_login(client, "a@dp6.com.br", now)

    client.collection.assert_called_once_with("login_events")
    collection.add.assert_called_once_with({"email": "a@dp6.com.br", "logged_in_at": now})


def test_list_login_events_filters_by_since_and_sorts_desc_in_python():
    client, collection = _fake_client_with_collection()
    filtered_query = MagicMock()
    collection.where.return_value = filtered_query
    older = _doc({"email": "a@dp6.com.br", "logged_in_at": datetime(2026, 1, 1, tzinfo=UTC)})
    newer = _doc({"email": "b@dp6.com.br", "logged_in_at": datetime(2026, 6, 1, tzinfo=UTC)})
    filtered_query.stream.return_value = [older, newer]

    since = datetime(2025, 12, 1, tzinfo=UTC)
    result = repository.list_login_events(client, since)

    collection.where.assert_called_once()
    assert [e["email"] for e in result] == ["b@dp6.com.br", "a@dp6.com.br"]


def test_list_all_favorites_derives_owner_email_from_parent_doc():
    client = MagicMock()
    collection_group = MagicMock()
    client.collection_group.return_value = collection_group
    collection_group.stream.return_value = [
        _doc(
            {"project_id": "proj", "dataset_id": "RAW", "table_id": "events"},
            owner_email="a@dp6.com.br",
        ),
    ]

    result = repository.list_all_favorites(client)

    client.collection_group.assert_called_once_with("favorites")
    assert result == [
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "owner_email": "a@dp6.com.br",
        }
    ]


def test_list_all_profiling_runs_scans_collection_group():
    client = MagicMock()
    collection_group = MagicMock()
    client.collection_group.return_value = collection_group
    collection_group.stream.return_value = [
        _doc({"project_id": "proj", "dataset_id": "RAW", "table_id": "events"}),
    ]

    result = repository.list_all_profiling_runs(client)

    client.collection_group.assert_called_once_with("runs")
    assert result == [{"project_id": "proj", "dataset_id": "RAW", "table_id": "events"}]


def test_list_all_table_views_derives_owner_email_from_parent_doc():
    client = MagicMock()
    collection_group = MagicMock()
    client.collection_group.return_value = collection_group
    collection_group.stream.return_value = [
        _doc(
            {"project_id": "proj", "dataset_id": "RAW", "table_id": "events"},
            owner_email="a@dp6.com.br",
        ),
    ]

    result = repository.list_all_table_views(client)

    client.collection_group.assert_called_once_with("history_table_views")
    assert result[0]["owner_email"] == "a@dp6.com.br"


def test_list_all_searches_derives_owner_email_from_parent_doc():
    client = MagicMock()
    collection_group = MagicMock()
    client.collection_group.return_value = collection_group
    collection_group.stream.return_value = [
        _doc({"query": "crm_leads", "mode": "table"}, owner_email="a@dp6.com.br"),
    ]

    result = repository.list_all_searches(client)

    client.collection_group.assert_called_once_with("history_searches")
    assert result[0]["owner_email"] == "a@dp6.com.br"


def test_list_all_pii_scans_scans_collection_group_named_scans():
    client = MagicMock()
    collection_group = MagicMock()
    client.collection_group.return_value = collection_group
    collection_group.stream.return_value = [
        _doc({"project_id": "proj", "dataset_id": "RAW", "table_id": "clientes"}),
    ]

    result = repository.list_all_pii_scans(client)

    client.collection_group.assert_called_once_with("scans")
    assert result == [{"project_id": "proj", "dataset_id": "RAW", "table_id": "clientes"}]
