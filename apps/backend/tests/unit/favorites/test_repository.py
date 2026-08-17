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


def _doc(data: dict | None, exists: bool = True) -> MagicMock:
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data
    return snapshot


def test_favorite_doc_id_with_table_is_deterministic():
    assert repository._favorite_doc_id("proj", "RAW", "events") == "proj__RAW__events"


def test_favorite_doc_id_without_table_has_two_segments():
    assert repository._favorite_doc_id("proj", "RAW") == "proj__RAW"
    assert repository._favorite_doc_id("proj", "RAW", None) == "proj__RAW"


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


def test_add_favorite_table_sets_deterministic_doc_id_with_added_at():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    result = repository.add_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    favorites_collection.document.assert_called_once_with("proj__RAW__events")
    doc_ref.set.assert_called_once()
    set_data = doc_ref.set.call_args[0][0]
    assert set_data["project_id"] == "proj"
    assert set_data["dataset_id"] == "RAW"
    assert set_data["table_id"] == "events"
    assert set_data["nickname"] is None
    assert isinstance(set_data["added_at"], datetime)
    assert set_data["added_at"].tzinfo is UTC
    assert result == set_data


def test_add_favorite_dataset_uses_two_segment_doc_id_and_null_table():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    result = repository.add_favorite(client, "a@dp6.com.br", "proj", "RAW")

    favorites_collection.document.assert_called_once_with("proj__RAW")
    assert result["table_id"] is None


def test_add_favorite_preserves_added_at_on_repeat_call():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref
    original_added_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc_ref.get.return_value = _doc(
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "nickname": None,
            "added_at": original_added_at,
        },
        exists=True,
    )

    result = repository.add_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    assert result["added_at"] == original_added_at


def test_add_favorite_with_nickname_none_preserves_existing_nickname():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "nickname": "Meu apelido",
            "added_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
        exists=True,
    )

    # nickname=None (default) é o caminho do toggle de favorito — nunca
    # deve apagar um apelido já salvo.
    result = repository.add_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    assert result["nickname"] == "Meu apelido"


def test_add_favorite_with_new_nickname_overwrites_existing():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "nickname": "Antigo",
            "added_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
        exists=True,
    )

    result = repository.add_favorite(
        client, "a@dp6.com.br", "proj", "RAW", "events", nickname="Novo apelido"
    )

    assert result["nickname"] == "Novo apelido"


def test_add_favorite_with_empty_string_nickname_clears_it():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(
        {
            "project_id": "proj",
            "dataset_id": "RAW",
            "table_id": "events",
            "nickname": "Antigo",
            "added_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
        exists=True,
    )

    result = repository.add_favorite(client, "a@dp6.com.br", "proj", "RAW", "events", nickname="")

    assert result["nickname"] is None


def test_remove_table_favorite_deletes_by_three_segment_doc_id():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref

    repository.remove_favorite(client, "a@dp6.com.br", "proj", "RAW", "events")

    favorites_collection.document.assert_called_once_with("proj__RAW__events")
    doc_ref.delete.assert_called_once()


def test_remove_dataset_favorite_deletes_by_two_segment_doc_id():
    client, favorites_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    favorites_collection.document.return_value = doc_ref

    repository.remove_favorite(client, "a@dp6.com.br", "proj", "RAW")

    favorites_collection.document.assert_called_once_with("proj__RAW")
    doc_ref.delete.assert_called_once()
