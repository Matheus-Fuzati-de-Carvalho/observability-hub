from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.cloud import firestore

from observability_hub.domains.favorites import repository


def _fake_client_with_collection():
    """MagicMock cujo client.collection("users").document(email)
    .collection("favorites") devolve um MagicMock capturável — cada
    teste configura o comportamento específico (stream/set/delete) nesse
    mock de coleção."""
    client = MagicMock()
    users_collection = MagicMock()
    user_doc = MagicMock()
    favorites_collection = MagicMock()

    client.collection.return_value = users_collection
    users_collection.document.return_value = user_doc
    user_doc.collection.return_value = favorites_collection

    return client, favorites_collection


def _doc(data: dict) -> MagicMock:
    snapshot = MagicMock()
    snapshot.to_dict.return_value = data
    return snapshot


def test_favorite_doc_id_is_deterministic():
    assert repository._favorite_doc_id("proj", "RAW", "events") == "proj__RAW__events"


def test_list_favorites_queries_collection_ordered_desc():
    client, favorites_collection = _fake_client_with_collection()
    ordered_query = MagicMock()
    favorites_collection.order_by.return_value = ordered_query
    ordered_query.stream.return_value = [
        _doc({"project_id": "proj", "dataset_id": "RAW", "table_id": "events"}),
    ]

    result = repository.list_favorites(client, "a@dp6.com.br")

    client.collection.assert_called_once_with("users")
    favorites_collection.order_by.assert_called_once_with(
        "added_at", direction=firestore.Query.DESCENDING
    )
    assert result == [{"project_id": "proj", "dataset_id": "RAW", "table_id": "events"}]


def test_add_favorite_sets_deterministic_doc_id_with_added_at():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref

    result = repository.add_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    favorites_collection.document.assert_called_once_with("proj__RAW__events")
    doc_ref.set.assert_called_once()
    set_data = doc_ref.set.call_args[0][0]
    assert set_data["project_id"] == "proj"
    assert set_data["dataset_id"] == "RAW"
    assert set_data["table_id"] == "events"
    assert isinstance(set_data["added_at"], datetime)
    assert set_data["added_at"].tzinfo is UTC
    assert result == set_data


def test_remove_favorite_deletes_by_deterministic_doc_id():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref

    repository.remove_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    favorites_collection.document.assert_called_once_with("proj__RAW__events")
    doc_ref.delete.assert_called_once()
