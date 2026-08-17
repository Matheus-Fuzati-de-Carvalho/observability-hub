from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.admin import repository


def _fake_client_with_collection():
    client = MagicMock()
    users_collection = MagicMock()
    client.collection.return_value = users_collection
    return client, users_collection


def _fake_multi_collection_client():
    """client.collection(name) devolve um MagicMock diferente por nome —
    necessário pros testes que tocam mais de uma coleção (hub_projects,
    access_requests, e users_with_project_access que lê hub_users).
    Pré-criado (não lazy) pra o teste poder configurar o mock antes de
    chamar a função do repository que o usa."""
    collections: dict[str, MagicMock] = {
        "hub_users": MagicMock(),
        "hub_projects": MagicMock(),
        "access_requests": MagicMock(),
    }
    client = MagicMock()
    client.collection.side_effect = lambda name: collections[name]
    return client, collections


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


# --- users_with_project_access ----------------------------------------------------


def test_users_with_project_access_queries_array_contains_any():
    client, collections = _fake_multi_collection_client()
    users_collection = collections["hub_users"]
    filtered_query = MagicMock()
    users_collection.where.return_value = filtered_query
    filtered_query.stream.return_value = [
        _doc({"email": "a@dp6.com.br", "allowed_projects": ["proj-a"]}, exists=True),
    ]

    result = repository.users_with_project_access(client, "proj-a")

    users_collection.where.assert_called_once()
    assert result == [{"email": "a@dp6.com.br", "allowed_projects": ["proj-a"]}]


# --- hub_projects ------------------------------------------------------------------


def test_get_project_returns_dict_when_exists():
    client, collections = _fake_multi_collection_client()
    projects_collection = collections["hub_projects"]
    doc_ref = MagicMock()
    projects_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc({"project_id": "proj-a", "is_public": True}, exists=True)

    result = repository.get_project(client, "proj-a")

    assert result == {"project_id": "proj-a", "is_public": True}


def test_get_project_returns_none_when_missing():
    client, collections = _fake_multi_collection_client()
    projects_collection = collections["hub_projects"]
    doc_ref = MagicMock()
    projects_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    assert repository.get_project(client, "ghost-proj") is None


def test_list_projects_orders_by_project_id():
    client, collections = _fake_multi_collection_client()
    projects_collection = collections["hub_projects"]
    ordered_query = MagicMock()
    projects_collection.order_by.return_value = ordered_query
    ordered_query.stream.return_value = [_doc({"project_id": "proj-a"}, exists=True)]

    result = repository.list_projects(client)

    projects_collection.order_by.assert_called_once_with("project_id")
    assert result == [{"project_id": "proj-a"}]


def test_upsert_project_preserves_created_at_on_existing():
    client, collections = _fake_multi_collection_client()
    projects_collection = collections["hub_projects"]
    doc_ref = MagicMock()
    projects_collection.document.return_value = doc_ref
    original_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc_ref.get.return_value = _doc(
        {"project_id": "proj-a", "created_at": original_created_at}, exists=True
    )

    result = repository.upsert_project(client, "proj-a", True, updated_by="admin@dp6.com.br")

    assert result["created_at"] == original_created_at
    assert result["is_public"] is True
    doc_ref.set.assert_called_once_with(result)


def test_upsert_project_sets_created_at_on_new():
    client, collections = _fake_multi_collection_client()
    projects_collection = collections["hub_projects"]
    doc_ref = MagicMock()
    projects_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    result = repository.upsert_project(client, "proj-new", False, updated_by="admin@dp6.com.br")

    assert result["created_at"] == result["updated_at"]


# --- access_requests -----------------------------------------------------------------


def test_create_access_request_uses_auto_generated_doc_id():
    client, collections = _fake_multi_collection_client()
    requests_collection = collections["access_requests"]
    doc_ref = MagicMock()
    doc_ref.id = "auto-id-123"
    requests_collection.document.return_value = doc_ref

    now = datetime(2026, 8, 20, tzinfo=UTC)
    result = repository.create_access_request(client, "a@dp6.com.br", "proj-a", now)

    requests_collection.document.assert_called_once_with()
    assert result["request_id"] == "auto-id-123"
    assert result["email"] == "a@dp6.com.br"
    assert result["project_id"] == "proj-a"
    assert result["status"] == "pending"
    assert result["requested_at"] == now
    doc_ref.set.assert_called_once_with(result)


def test_list_access_requests_sorts_by_requested_at_descending():
    client, collections = _fake_multi_collection_client()
    requests_collection = collections["access_requests"]
    older = _doc({"request_id": "r1", "requested_at": datetime(2026, 1, 1, tzinfo=UTC)}, True)
    newer = _doc({"request_id": "r2", "requested_at": datetime(2026, 6, 1, tzinfo=UTC)}, True)
    requests_collection.stream.return_value = [older, newer]

    result = repository.list_access_requests(client)

    assert [r["request_id"] for r in result] == ["r2", "r1"]


def test_list_access_requests_filters_by_status():
    client, collections = _fake_multi_collection_client()
    requests_collection = collections["access_requests"]
    filtered_query = MagicMock()
    requests_collection.where.return_value = filtered_query
    filtered_query.stream.return_value = [
        _doc({"request_id": "r1", "status": "pending", "requested_at": datetime.now(UTC)}, True)
    ]

    result = repository.list_access_requests(client, status="pending")

    requests_collection.where.assert_called_once()
    assert result[0]["request_id"] == "r1"


def test_has_pending_request_true_when_match_found():
    client, collections = _fake_multi_collection_client()
    requests_collection = collections["access_requests"]
    filtered_query = MagicMock()
    requests_collection.where.return_value = filtered_query
    filtered_query.stream.return_value = [
        _doc({"project_id": "proj-a", "status": "pending"}, True),
        _doc({"project_id": "proj-b", "status": "denied"}, True),
    ]

    assert repository.has_pending_request(client, "a@dp6.com.br", "proj-a") is True


def test_has_pending_request_false_when_no_match():
    client, collections = _fake_multi_collection_client()
    requests_collection = collections["access_requests"]
    filtered_query = MagicMock()
    requests_collection.where.return_value = filtered_query
    filtered_query.stream.return_value = [
        _doc({"project_id": "proj-b", "status": "pending"}, True),
    ]

    assert repository.has_pending_request(client, "a@dp6.com.br", "proj-a") is False


def test_get_access_request_returns_none_when_missing():
    client, collections = _fake_multi_collection_client()
    requests_collection = collections["access_requests"]
    doc_ref = MagicMock()
    requests_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    assert repository.get_access_request(client, "ghost-id") is None


def test_update_access_request_status_updates_and_returns_fresh_doc():
    client, collections = _fake_multi_collection_client()
    requests_collection = collections["access_requests"]
    doc_ref = MagicMock()
    requests_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc({"request_id": "r1", "status": "approved"}, exists=True)

    now = datetime(2026, 8, 20, tzinfo=UTC)
    result = repository.update_access_request_status(
        client, "r1", "approved", "admin@dp6.com.br", now
    )

    doc_ref.update.assert_called_once_with(
        {"status": "approved", "resolved_at": now, "resolved_by": "admin@dp6.com.br"}
    )
    assert result == {"request_id": "r1", "status": "approved"}
