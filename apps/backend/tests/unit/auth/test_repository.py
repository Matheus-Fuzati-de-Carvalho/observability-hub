from unittest.mock import MagicMock, patch

from observability_hub.domains.auth import repository


def test_build_authorize_url_uses_oauth_session(monkeypatch):
    monkeypatch.setattr(repository.secrets, "get_oauth_client_id", lambda: "client-id")
    monkeypatch.setattr(repository.secrets, "get_oauth_client_secret", lambda: "client-secret")

    fake_session = MagicMock()
    fake_session.create_authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/v2/auth?...",
        "state123",
    )

    with patch.object(repository, "OAuth2Session", return_value=fake_session) as mock_cls:
        url = repository.build_authorize_url(
            "https://frontend.example.com/auth/callback", "state123"
        )

    assert url == "https://accounts.google.com/o/oauth2/v2/auth?..."
    mock_cls.assert_called_once_with(
        "client-id",
        "client-secret",
        scope=repository._SCOPES,
        redirect_uri="https://frontend.example.com/auth/callback",
    )
    fake_session.create_authorization_url.assert_called_once_with(
        repository._AUTHORIZE_URL, state="state123"
    )


def test_build_authorize_url_forwards_prompt_as_extra_param(monkeypatch):
    monkeypatch.setattr(repository.secrets, "get_oauth_client_id", lambda: "client-id")
    monkeypatch.setattr(repository.secrets, "get_oauth_client_secret", lambda: "client-secret")

    fake_session = MagicMock()
    fake_session.create_authorization_url.return_value = ("https://accounts.google.com/...", "s")

    with patch.object(repository, "OAuth2Session", return_value=fake_session):
        repository.build_authorize_url(
            "https://frontend.example.com/auth/callback", "state123", prompt="select_account"
        )

    fake_session.create_authorization_url.assert_called_once_with(
        repository._AUTHORIZE_URL, state="state123", prompt="select_account"
    )


def test_fetch_userinfo_exchanges_code_and_returns_json(monkeypatch):
    monkeypatch.setattr(repository.secrets, "get_oauth_client_id", lambda: "client-id")
    monkeypatch.setattr(repository.secrets, "get_oauth_client_secret", lambda: "client-secret")

    fake_session = MagicMock()
    fake_response = MagicMock()
    fake_response.json.return_value = {"email": "a@dp6.com.br", "name": "A"}
    fake_session.get.return_value = fake_response

    with patch.object(repository, "OAuth2Session", return_value=fake_session):
        result = repository.fetch_userinfo(
            "auth-code", "https://frontend.example.com/auth/callback"
        )

    fake_session.fetch_token.assert_called_once_with(
        repository._TOKEN_URL, code="auth-code", grant_type="authorization_code"
    )
    fake_session.get.assert_called_once_with(repository._USERINFO_URL)
    fake_response.raise_for_status.assert_called_once()
    assert result == {"email": "a@dp6.com.br", "name": "A"}
