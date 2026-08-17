from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import AccessRequestNotFoundError, LastAdminLockoutError
from observability_hub.domains.admin import service
from observability_hub.domains.admin.schemas import UpsertHubProjectRequest, UpsertHubUserRequest


def _fake_client() -> MagicMock:
    return MagicMock(name="firestore.Client")


# --- list_users --------------------------------------------------------------


def test_list_users_builds_response(monkeypatch):
    raw = [
        {
            "email": "a@dp6.com.br",
            "is_admin": True,
            "allowed_projects": ["*"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": "a@dp6.com.br",
        }
    ]
    monkeypatch.setattr(service.repository, "list_users", lambda client: raw)

    result = service.list_users(_fake_client())

    assert len(result.users) == 1
    assert result.users[0].email == "a@dp6.com.br"


# --- upsert_user ---------------------------------------------------------------


def test_upsert_user_normalizes_email_and_updated_by(monkeypatch):
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured.update(
            email=email, is_admin=is_admin, allowed_projects=allowed_projects, updated_by=updated_by
        )
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    result = service.upsert_user(
        _fake_client(),
        "A@DP6.com.br",
        UpsertHubUserRequest(is_admin=False, allowed_projects=["proj-a"]),
        updated_by="ADMIN@dp6.com.br",
    )

    assert captured["email"] == "a@dp6.com.br"
    assert captured["updated_by"] == "admin@dp6.com.br"
    assert result.email == "a@dp6.com.br"


def test_upsert_user_allows_demoting_admin_when_other_admins_remain(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": True},
    )
    monkeypatch.setattr(
        service.repository,
        "list_users",
        lambda client: [
            {"email": "a@dp6.com.br", "is_admin": True},
            {"email": "b@dp6.com.br", "is_admin": True},
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "upsert_user",
        lambda client, email, is_admin, allowed_projects, updated_by: {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": updated_by,
        },
    )

    result = service.upsert_user(
        _fake_client(),
        "a@dp6.com.br",
        UpsertHubUserRequest(is_admin=False, allowed_projects=[]),
        updated_by="b@dp6.com.br",
    )

    assert result.is_admin is False


def test_upsert_user_blocks_demoting_last_admin(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": True},
    )
    monkeypatch.setattr(
        service.repository,
        "list_users",
        lambda client: [{"email": "a@dp6.com.br", "is_admin": True}],
    )

    with pytest.raises(LastAdminLockoutError):
        service.upsert_user(
            _fake_client(),
            "a@dp6.com.br",
            UpsertHubUserRequest(is_admin=False, allowed_projects=[]),
            updated_by="a@dp6.com.br",
        )


# --- delete_user ---------------------------------------------------------------


def test_delete_user_blocks_deleting_last_admin(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": True},
    )
    monkeypatch.setattr(
        service.repository,
        "list_users",
        lambda client: [{"email": "a@dp6.com.br", "is_admin": True}],
    )

    with pytest.raises(LastAdminLockoutError):
        service.delete_user(_fake_client(), "a@dp6.com.br")


def test_delete_user_allows_deleting_non_admin(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": False},
    )
    delete_mock = MagicMock()
    monkeypatch.setattr(service.repository, "delete_user", delete_mock)

    service.delete_user(_fake_client(), "a@dp6.com.br")

    assert delete_mock.call_args[0][1] == "a@dp6.com.br"


def test_delete_user_is_idempotent_for_unknown_email(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    delete_mock = MagicMock()
    monkeypatch.setattr(service.repository, "delete_user", delete_mock)

    service.delete_user(_fake_client(), "ghost@dp6.com.br")

    delete_mock.assert_called_once()


# --- is_admin --------------------------------------------------------------------


def test_is_admin_true_when_flagged(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: {"is_admin": True})
    assert service.is_admin(_fake_client(), "a@dp6.com.br") is True


def test_is_admin_false_when_no_doc(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    assert service.is_admin(_fake_client(), "ghost@dp6.com.br") is False


def test_is_admin_normalizes_email_case(monkeypatch):
    seen = {}

    def fake_get_user(client, email):
        seen["email"] = email
        return {"is_admin": True}

    monkeypatch.setattr(service.repository, "get_user", fake_get_user)

    service.is_admin(_fake_client(), "A@DP6.com.br")

    assert seen["email"] == "a@dp6.com.br"


# --- has_project_access -----------------------------------------------------------


def _stub_no_public_project(monkeypatch):
    """Default pra quem não é o foco do teste: nenhum projeto marcado
    is_public. Sem isso, MagicMock().get("is_public") é truthy por
    padrão e todo teste de has_project_access que não mocka get_project
    passaria por engano (fail-closed quebrado)."""
    monkeypatch.setattr(service.repository, "get_project", lambda client, project_id: None)


def test_has_project_access_false_when_no_doc(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    assert service.has_project_access(_fake_client(), "ghost@dp6.com.br", "proj-a") is False


def test_has_project_access_true_for_wildcard(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["*"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "any-project") is True


def test_has_project_access_true_for_explicit_project(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["proj-a", "proj-b"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a") is True


def test_has_project_access_false_for_project_not_in_list(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["proj-a"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-c") is False


def test_has_project_access_true_when_project_is_public(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": True}
    )
    get_user_mock = MagicMock()
    monkeypatch.setattr(service.repository, "get_user", get_user_mock)

    result = service.has_project_access(_fake_client(), "ghost@dp6.com.br", "proj-a")

    assert result is True
    # is_public já resolveu — nem precisa olhar o usuário.
    get_user_mock.assert_not_called()


def test_has_project_access_false_when_project_exists_but_not_public(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": False}
    )
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)

    assert service.has_project_access(_fake_client(), "ghost@dp6.com.br", "proj-a") is False


# --- hub_projects ------------------------------------------------------------------


def test_list_projects_builds_response(monkeypatch):
    raw = [
        {
            "project_id": "proj-a",
            "is_public": True,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": "admin@dp6.com.br",
        }
    ]
    monkeypatch.setattr(service.repository, "list_projects", lambda client: raw)

    result = service.list_projects(_fake_client())

    assert len(result.projects) == 1
    assert result.projects[0].project_id == "proj-a"


def test_upsert_project_delegates_to_repository(monkeypatch):
    captured = {}

    def fake_upsert(client, project_id, is_public, updated_by):
        captured.update(project_id=project_id, is_public=is_public, updated_by=updated_by)
        return {
            "project_id": project_id,
            "is_public": is_public,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_project", fake_upsert)

    result = service.upsert_project(
        _fake_client(),
        "proj-a",
        UpsertHubProjectRequest(is_public=True),
        updated_by="ADMIN@dp6.com.br",
    )

    assert captured["project_id"] == "proj-a"
    assert captured["updated_by"] == "admin@dp6.com.br"
    assert result.is_public is True


def test_get_project_users_marks_wildcard_vs_explicit(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": False}
    )
    monkeypatch.setattr(
        service.repository,
        "users_with_project_access",
        lambda client, project_id: [
            {"email": "explicit@dp6.com.br", "is_admin": False, "allowed_projects": ["proj-a"]},
            {"email": "wild@dp6.com.br", "is_admin": True, "allowed_projects": ["*"]},
        ],
    )

    result = service.get_project_users(_fake_client(), "proj-a")

    assert result.is_public is False
    by_email = {u.email: u for u in result.users}
    assert by_email["explicit@dp6.com.br"].granted_via == "explicit"
    assert by_email["wild@dp6.com.br"].granted_via == "wildcard"


def test_get_project_users_reflects_is_public(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": True}
    )
    monkeypatch.setattr(
        service.repository, "users_with_project_access", lambda client, project_id: []
    )

    result = service.get_project_users(_fake_client(), "proj-a")

    assert result.is_public is True
    assert result.users == []


def test_grant_project_to_user_creates_new_user(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured.update(
            email=email, is_admin=is_admin, allowed_projects=allowed_projects, updated_by=updated_by
        )
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    result = service.grant_project_to_user(
        _fake_client(), "proj-a", "new@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert captured["is_admin"] is False
    assert captured["allowed_projects"] == ["proj-a"]
    assert result.allowed_projects == ["proj-a"]


def test_grant_project_to_user_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {
            "email": email,
            "is_admin": False,
            "allowed_projects": ["proj-a", "proj-b"],
        },
    )
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured["allowed_projects"] = allowed_projects
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    service.grant_project_to_user(
        _fake_client(), "proj-a", "a@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert captured["allowed_projects"] == ["proj-a", "proj-b"]


def test_revoke_project_from_user_removes_only_that_project(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {
            "email": email,
            "is_admin": False,
            "allowed_projects": ["proj-a", "proj-b"],
        },
    )
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured["allowed_projects"] = allowed_projects
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    result = service.revoke_project_from_user(
        _fake_client(), "proj-a", "a@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert captured["allowed_projects"] == ["proj-b"]
    assert result.allowed_projects == ["proj-b"]


def test_revoke_project_from_user_returns_none_when_user_missing(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)

    result = service.revoke_project_from_user(
        _fake_client(), "proj-a", "ghost@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert result is None


# --- access_requests -----------------------------------------------------------------


def test_create_access_requests_skips_already_accessible_project(monkeypatch):
    monkeypatch.setattr(service, "has_project_access", lambda client, email, project_id: True)
    monkeypatch.setattr(
        service.repository, "has_pending_request", lambda client, email, project_id: False
    )
    create_mock = MagicMock()
    monkeypatch.setattr(service.repository, "create_access_request", create_mock)

    result = service.create_access_requests(_fake_client(), "a@dp6.com.br", ["proj-a"])

    assert result.requests == []
    create_mock.assert_not_called()


def test_create_access_requests_skips_duplicate_pending(monkeypatch):
    monkeypatch.setattr(service, "has_project_access", lambda client, email, project_id: False)
    monkeypatch.setattr(
        service.repository, "has_pending_request", lambda client, email, project_id: True
    )
    create_mock = MagicMock()
    monkeypatch.setattr(service.repository, "create_access_request", create_mock)

    result = service.create_access_requests(_fake_client(), "a@dp6.com.br", ["proj-a"])

    assert result.requests == []
    create_mock.assert_not_called()


def test_create_access_requests_creates_for_new_project(monkeypatch):
    monkeypatch.setattr(service, "has_project_access", lambda client, email, project_id: False)
    monkeypatch.setattr(
        service.repository, "has_pending_request", lambda client, email, project_id: False
    )

    def fake_create(client, email, project_id, now):
        return {
            "request_id": "r1",
            "email": email,
            "project_id": project_id,
            "status": "pending",
            "requested_at": now,
            "resolved_at": None,
            "resolved_by": None,
        }

    monkeypatch.setattr(service.repository, "create_access_request", fake_create)

    result = service.create_access_requests(_fake_client(), "A@DP6.com.br", ["proj-a"])

    assert len(result.requests) == 1
    assert result.requests[0].email == "a@dp6.com.br"
    assert result.requests[0].status == "pending"


def test_list_access_requests_builds_response(monkeypatch):
    raw = [
        {
            "request_id": "r1",
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": "pending",
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": None,
            "resolved_by": None,
        }
    ]
    monkeypatch.setattr(service.repository, "list_access_requests", lambda client, status: raw)

    result = service.list_access_requests(_fake_client(), status="pending")

    assert len(result.requests) == 1
    assert result.requests[0].request_id == "r1"


def test_approve_access_request_grants_project_and_marks_approved(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_access_request",
        lambda client, request_id: {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": "pending",
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": None,
            "resolved_by": None,
        },
    )
    grant_mock = MagicMock()
    monkeypatch.setattr(service, "grant_project_to_user", grant_mock)

    def fake_update(client, request_id, status, resolved_by, now):
        return {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": status,
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": now,
            "resolved_by": resolved_by,
        }

    monkeypatch.setattr(service.repository, "update_access_request_status", fake_update)

    result = service.approve_access_request(_fake_client(), "r1", resolved_by="admin@dp6.com.br")

    assert grant_mock.call_args[0][1:] == ("proj-a", "a@dp6.com.br", "admin@dp6.com.br")
    assert result.status == "approved"
    assert result.resolved_by == "admin@dp6.com.br"


def test_deny_access_request_does_not_grant_project(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_access_request",
        lambda client, request_id: {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": "pending",
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": None,
            "resolved_by": None,
        },
    )
    grant_mock = MagicMock()
    monkeypatch.setattr(service, "grant_project_to_user", grant_mock)

    def fake_update(client, request_id, status, resolved_by, now):
        return {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": status,
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": now,
            "resolved_by": resolved_by,
        }

    monkeypatch.setattr(service.repository, "update_access_request_status", fake_update)

    result = service.deny_access_request(_fake_client(), "r1", resolved_by="admin@dp6.com.br")

    grant_mock.assert_not_called()
    assert result.status == "denied"


def test_approve_access_request_raises_when_not_found(monkeypatch):
    monkeypatch.setattr(service.repository, "get_access_request", lambda client, request_id: None)

    with pytest.raises(AccessRequestNotFoundError):
        service.approve_access_request(_fake_client(), "ghost-id", resolved_by="admin@dp6.com.br")
