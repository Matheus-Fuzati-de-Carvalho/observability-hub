import pytest
from authlib.integrations.base_client.errors import OAuthError
from requests import RequestException

from observability_hub.core.exceptions import (
    InvalidSessionError,
    OAuthEmailNotAllowedError,
    OAuthExchangeError,
    OAuthStateMismatchError,
)
from observability_hub.domains.auth import service
from observability_hub.domains.auth.schemas import UserInfo


def test_generate_state_returns_nonempty_urlsafe_token():
    state = service.generate_state()
    assert isinstance(state, str)
    assert len(state) > 20


def test_build_redirect_uri_picks_first_https_origin(monkeypatch):
    monkeypatch.setattr(
        service.settings,
        "cors_origins",
        "https://frontend-995219021404.us-central1.run.app,https://frontend-46qbggr2oa-uc.a.run.app,http://localhost:5173",
    )

    assert (
        service.build_redirect_uri()
        == "https://frontend-995219021404.us-central1.run.app/auth/callback"
    )


def test_build_redirect_uri_falls_back_to_first_entry_without_https(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "http://localhost:5173")

    assert service.build_redirect_uri() == "http://localhost:5173/auth/callback"


def test_build_authorize_url_delegates_to_repository_and_forces_account_selector(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")
    captured = {}

    def fake_build_authorize_url(redirect_uri, state, prompt=None):
        captured["redirect_uri"] = redirect_uri
        captured["state"] = state
        captured["prompt"] = prompt
        return "https://accounts.google.com/authorize?..."

    monkeypatch.setattr(service.repository, "build_authorize_url", fake_build_authorize_url)

    url = service.build_authorize_url("state-123")

    assert url == "https://accounts.google.com/authorize?..."
    assert captured == {
        "redirect_uri": "https://frontend.example.com/auth/callback",
        "state": "state-123",
        "prompt": "select_account",
    }


def test_handle_callback_raises_on_missing_state_cookie(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")
    with pytest.raises(OAuthStateMismatchError):
        service.handle_callback("code", "state-123", None)


def test_handle_callback_raises_on_state_mismatch(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")
    with pytest.raises(OAuthStateMismatchError):
        service.handle_callback("code", "state-123", "different-state")


def test_handle_callback_happy_path_allowed_by_domain(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")
    monkeypatch.setattr(
        service.repository,
        "fetch_userinfo",
        lambda code, redirect_uri: {
            "email": "pessoa@dp6.com.br",
            "name": "Pessoa",
            "picture": "https://p.png",
        },
    )
    monkeypatch.setattr(
        service.secrets,
        "get_oauth_allowlist",
        lambda: {"allowed_domains": ["dp6.com.br"], "allowed_emails": []},
    )

    user = service.handle_callback("code", "state-123", "state-123")

    assert user == UserInfo(email="pessoa@dp6.com.br", name="Pessoa", picture="https://p.png")


def test_handle_callback_happy_path_allowed_by_email(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")
    monkeypatch.setattr(
        service.repository,
        "fetch_userinfo",
        lambda code, redirect_uri: {"email": "avulso@gmail.com", "name": "Avulso"},
    )
    monkeypatch.setattr(
        service.secrets,
        "get_oauth_allowlist",
        lambda: {"allowed_domains": ["dp6.com.br"], "allowed_emails": ["avulso@gmail.com"]},
    )

    user = service.handle_callback("code", "state-123", "state-123")

    assert user.email == "avulso@gmail.com"


def test_handle_callback_raises_when_email_not_allowed(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")
    monkeypatch.setattr(
        service.repository,
        "fetch_userinfo",
        lambda code, redirect_uri: {"email": "estranho@outrodominio.com", "name": "Estranho"},
    )
    monkeypatch.setattr(
        service.secrets,
        "get_oauth_allowlist",
        lambda: {"allowed_domains": ["dp6.com.br"], "allowed_emails": []},
    )

    with pytest.raises(OAuthEmailNotAllowedError):
        service.handle_callback("code", "state-123", "state-123")


@pytest.mark.parametrize("raised", [OAuthError("bad"), RequestException("network down")])
def test_handle_callback_wraps_exchange_failures(monkeypatch, raised):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")

    def fake_fetch_userinfo(code, redirect_uri):
        raise raised

    monkeypatch.setattr(service.repository, "fetch_userinfo", fake_fetch_userinfo)

    with pytest.raises(OAuthExchangeError):
        service.handle_callback("code", "state-123", "state-123")


def test_handle_callback_raises_when_userinfo_missing_email(monkeypatch):
    monkeypatch.setattr(service.settings, "cors_origins", "https://frontend.example.com")
    monkeypatch.setattr(
        service.repository, "fetch_userinfo", lambda code, redirect_uri: {"name": "Sem email"}
    )

    with pytest.raises(OAuthExchangeError):
        service.handle_callback("code", "state-123", "state-123")


def test_issue_and_decode_session_token_roundtrip(monkeypatch):
    monkeypatch.setattr(service.secrets, "get_jwt_secret", lambda: "test-secret")
    user = UserInfo(email="a@dp6.com.br", name="A", picture=None)

    token = service.issue_session_token(user)
    decoded = service.decode_session_token(token)

    assert decoded == user


def test_decode_session_token_raises_when_missing(monkeypatch):
    monkeypatch.setattr(service.secrets, "get_jwt_secret", lambda: "test-secret")
    with pytest.raises(InvalidSessionError):
        service.decode_session_token(None)


def test_decode_session_token_raises_when_garbage(monkeypatch):
    monkeypatch.setattr(service.secrets, "get_jwt_secret", lambda: "test-secret")
    with pytest.raises(InvalidSessionError):
        service.decode_session_token("not-a-jwt")


def test_decode_session_token_raises_when_signed_with_different_secret(monkeypatch):
    monkeypatch.setattr(service.secrets, "get_jwt_secret", lambda: "secret-a")
    token = service.issue_session_token(UserInfo(email="a@dp6.com.br", name="A"))

    monkeypatch.setattr(service.secrets, "get_jwt_secret", lambda: "secret-b")
    with pytest.raises(InvalidSessionError):
        service.decode_session_token(token)
