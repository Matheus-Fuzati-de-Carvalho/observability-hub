from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.admin import repository


def _fake_client_with_collection():
    client = MagicMock()
    users_collection = MagicMock()
    client.collection.return_value = users_collection
    return client, users_collection


def _doc(data: dict | None, exists: bool):
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data
    return snapshot


def test_get_user_returns_dict_when_doc_exists():
    client, users_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    users_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc({"email": "a@dp6.com.br", "is_admin": True}, exists=True)

    result = repository.get_user(client, "a@dp6.com.br")

    client.collection.assert_called_once_with("hub_users")
    users_collection.document.assert_called_once_with("a@dp6.com.br")
    assert result == {"email": "a@dp6.com.br", "is_admin": True}


def test_get_user_returns_none_when_doc_missing():
    client, users_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    users_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    assert repository.get_user(client, "ghost@dp6.com.br") is None


def test_list_users_orders_by_email():
    client, users_collection = _fake_client_with_collection()
    ordered_query = MagicMock()
    users_collection.order_by.return_value = ordered_query
    ordered_query.stream.return_value = [
        _doc({"email": "a@dp6.com.br"}, exists=True),
        _doc({"email": "b@dp6.com.br"}, exists=True),
    ]

    result = repository.list_users(client)

    users_collection.order_by.assert_called_once_with("email")
    assert result == [{"email": "a@dp6.com.br"}, {"email": "b@dp6.com.br"}]


def test_upsert_user_preserves_created_at_on_existing_user():
    client, users_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    users_collection.document.return_value = doc_ref
    original_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc_ref.get.return_value = _doc(
        {"email": "a@dp6.com.br", "created_at": original_created_at}, exists=True
    )

    result = repository.upsert_user(
        client, "a@dp6.com.br", True, ["proj-a"], updated_by="admin@dp6.com.br"
    )

    assert result["created_at"] == original_created_at
    assert isinstance(result["updated_at"], datetime)
    assert result["updated_at"].tzinfo is UTC
    assert result["is_admin"] is True
    assert result["allowed_projects"] == ["proj-a"]
    assert result["updated_by"] == "admin@dp6.com.br"
    doc_ref.set.assert_called_once_with(result)


def test_upsert_user_sets_created_at_on_new_user():
    client, users_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    users_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    result = repository.upsert_user(
        client, "new@dp6.com.br", False, [], updated_by="admin@dp6.com.br"
    )

    assert isinstance(result["created_at"], datetime)
    assert result["created_at"] == result["updated_at"]


def test_delete_user_deletes_by_email():
    client, users_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    users_collection.document.return_value = doc_ref

    repository.delete_user(client, "a@dp6.com.br")

    users_collection.document.assert_called_once_with("a@dp6.com.br")
    doc_ref.delete.assert_called_once()
