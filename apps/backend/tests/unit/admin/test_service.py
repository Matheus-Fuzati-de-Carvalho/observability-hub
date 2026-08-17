from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import LastAdminLockoutError
from observability_hub.domains.admin import service
from observability_hub.domains.admin.schemas import UpsertHubUserRequest


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


def test_has_project_access_false_when_no_doc(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    assert service.has_project_access(_fake_client(), "ghost@dp6.com.br", "proj-a") is False


def test_has_project_access_true_for_wildcard(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["*"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "any-project") is True


def test_has_project_access_true_for_explicit_project(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["proj-a", "proj-b"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a") is True


def test_has_project_access_false_for_project_not_in_list(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["proj-a"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-c") is False
