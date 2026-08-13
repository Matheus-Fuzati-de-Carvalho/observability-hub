import pytest

from observability_hub.core import auth as auth_module
from observability_hub.core.exceptions import InvalidSessionError
from observability_hub.domains.auth.schemas import UserInfo


def test_get_current_user_decodes_session_cookie(monkeypatch):
    expected = UserInfo(email="a@dp6.com.br", name="A")
    monkeypatch.setattr(auth_module.service, "decode_session_token", lambda token: expected)

    result = auth_module.get_current_user(session="a-valid-jwt")

    assert result == expected


def test_get_current_user_raises_when_cookie_missing(monkeypatch):
    def fake_decode(token):
        assert token is None
        raise InvalidSessionError()

    monkeypatch.setattr(auth_module.service, "decode_session_token", fake_decode)

    with pytest.raises(InvalidSessionError):
        auth_module.get_current_user(session=None)
