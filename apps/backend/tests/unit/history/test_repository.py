from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.cloud import firestore

from observability_hub.domains.history import repository


def _fake_client_with_collections():
    """MagicMock cujo client.collection("users").document(email)
    .collection(<nome>) devolve mocks distintos por nome de subcoleção —
    cada teste configura o comportamento específico (add/order_by/stream)
    na subcoleção que importa."""
    client = MagicMock()
    users_collection = MagicMock()
    user_doc = MagicMock()
    collections_by_name: dict[str, MagicMock] = {}

    def _collection(name: str) -> MagicMock:
        return collections_by_name.setdefault(name, MagicMock())

    client.collection.return_value = users_collection
    users_collection.document.return_value = user_doc
    user_doc.collection.side_effect = _collection

    return client, collections_by_name


def _doc(data: dict) -> MagicMock:
    snapshot = MagicMock()
    snapshot.to_dict.return_value = data
    return snapshot


def test_add_table_view_writes_then_trims():
    client, collections = _fake_client_with_collections()
    table_views = collections.setdefault("history_table_views", MagicMock())
    trimmed_query = MagicMock()
    table_views.order_by.return_value = trimmed_query
    trimmed_query.offset.return_value = trimmed_query
    trimmed_query.stream.return_value = []

    repository.add_table_view(client, "a@dp6.com.br", "proj", "RAW", "events")

    table_views.add.assert_called_once()
    added_data = table_views.add.call_args[0][0]
    assert added_data["project_id"] == "proj"
    assert added_data["dataset_id"] == "RAW"
    assert added_data["table_id"] == "events"
    assert isinstance(added_data["viewed_at"], datetime)
    assert added_data["viewed_at"].tzinfo is UTC

    table_views.order_by.assert_called_once_with("viewed_at", direction=firestore.Query.DESCENDING)
    trimmed_query.offset.assert_called_once_with(20)


def test_trim_to_max_deletes_only_overflow_docs():
    client, collections = _fake_client_with_collections()
    searches = collections.setdefault("history_searches", MagicMock())
    trimmed_query = MagicMock()
    searches.order_by.return_value = trimmed_query
    trimmed_query.offset.return_value = trimmed_query
    overflow_doc_1 = MagicMock()
    overflow_doc_2 = MagicMock()
    trimmed_query.stream.return_value = [overflow_doc_1, overflow_doc_2]

    repository.add_search(client, "a@dp6.com.br", "events_20260812", "exact", "proj")

    overflow_doc_1.reference.delete.assert_called_once()
    overflow_doc_2.reference.delete.assert_called_once()


def test_list_recent_table_views_orders_desc_and_limits():
    client, collections = _fake_client_with_collections()
    table_views = collections.setdefault("history_table_views", MagicMock())
    ordered_query = MagicMock()
    limited_query = MagicMock()
    table_views.order_by.return_value = ordered_query
    ordered_query.limit.return_value = limited_query
    limited_query.stream.return_value = [
        _doc(
            {
                "project_id": "proj",
                "dataset_id": "RAW",
                "table_id": "events",
                "viewed_at": datetime(2026, 8, 12, tzinfo=UTC),
            }
        )
    ]

    result = repository.list_recent_table_views(client, "a@dp6.com.br")

    table_views.order_by.assert_called_once_with("viewed_at", direction=firestore.Query.DESCENDING)
    ordered_query.limit.assert_called_once_with(20)
    assert result[0]["table_id"] == "events"


def test_list_recent_searches_orders_desc_and_limits():
    client, collections = _fake_client_with_collections()
    searches = collections.setdefault("history_searches", MagicMock())
    ordered_query = MagicMock()
    limited_query = MagicMock()
    searches.order_by.return_value = ordered_query
    ordered_query.limit.return_value = limited_query
    limited_query.stream.return_value = [
        _doc(
            {
                "query": "events_20260812",
                "mode": "exact",
                "project_id": "proj",
                "searched_at": datetime(2026, 8, 12, tzinfo=UTC),
            }
        )
    ]

    result = repository.list_recent_searches(client, "a@dp6.com.br")

    searches.order_by.assert_called_once_with("searched_at", direction=firestore.Query.DESCENDING)
    ordered_query.limit.assert_called_once_with(20)
    assert result[0]["query"] == "events_20260812"
