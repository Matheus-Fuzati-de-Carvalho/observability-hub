"""Orquestra o domínio auth: fluxo OAuth (login/callback), emissão/
validação de JWT de sessão, checagem de allowlist. api/v1/auth.py só
chama estas funções — CLAUDE.md proíbe lógica de negócio em api/.
"""

import secrets as token_secrets
from datetime import UTC, datetime, timedelta

from authlib.integrations.base_client.errors import OAuthError
from jose import JWTError, jwt
from requests import RequestException

from observability_hub.core import secrets
from observability_hub.core.config import settings
from observability_hub.core.exceptions import (
    InvalidSessionError,
    OAuthEmailNotAllowedError,
    OAuthExchangeError,
    OAuthStateMismatchError,
)
from observability_hub.domains.auth import repository
from observability_hub.domains.auth.schemas import UserInfo

STATE_COOKIE_NAME = "oauth_state"
SESSION_COOKIE_NAME = "session"
SESSION_COOKIE_MAX_AGE_SECONDS = 12 * 60 * 60
STATE_COOKIE_MAX_AGE_SECONDS = 10 * 60  # janela curta — só entre /login e /callback
_JWT_ALGORITHM = "HS256"


def generate_state() -> str:
    return token_secrets.token_urlsafe(32)


def build_redirect_uri() -> str:
    """Uma única URL de callback por ambiente (a primeira https:// de
    cors_origins_list — mesma lista já usada pro CORS, ambas as URLs do
    Cloud Run de cada ambiente estão registradas no Google OAuth, mas só
    uma precisa ser usada de forma consistente aqui). Não depende de
    Origin/Referer do request: mais simples e sem casos de borda de
    header ausente/estripado."""
    for origin in settings.cors_origins_list:
        if origin.startswith("https://"):
            return f"{origin}/auth/callback"
    return f"{settings.cors_origins_list[0]}/auth/callback"


def build_authorize_url(state: str) -> str:
    # select_account força o Google a sempre mostrar o seletor de contas,
    # mesmo com uma sessão do Google já ativa no browser — sem isso, depois
    # de um logout do Hub (que não afeta a sessão do Google em si), clicar
    # em "Entrar com Google" de novo autentica silenciosamente com a mesma
    # conta, sem dar a chance de escolher outra.
    return repository.build_authorize_url(build_redirect_uri(), state, prompt="select_account")


def _is_email_allowed(email: str, allowlist: dict) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    allowed_domains = {d.lower() for d in allowlist.get("allowed_domains", [])}
    allowed_emails = {e.lower() for e in allowlist.get("allowed_emails", [])}
    return domain in allowed_domains or email.lower() in allowed_emails


def handle_callback(code: str, state: str, state_cookie: str | None) -> UserInfo:
    if not state_cookie or state != state_cookie:
        raise OAuthStateMismatchError()

    try:
        userinfo = repository.fetch_userinfo(code, build_redirect_uri())
    except (OAuthError, RequestException) as exc:
        raise OAuthExchangeError(str(exc)) from exc

    email = userinfo.get("email")
    if not email:
        raise OAuthExchangeError("resposta do Google não trouxe email")

    if not _is_email_allowed(email, secrets.get_oauth_allowlist()):
        raise OAuthEmailNotAllowedError(email)

    return UserInfo(
        email=email, name=userinfo.get("name") or email, picture=userinfo.get("picture")
    )


def issue_session_token(user: UserInfo) -> str:
    payload = {
        "sub": user.email,
        "name": user.name,
        "picture": user.picture,
        "exp": datetime.now(UTC) + timedelta(seconds=SESSION_COOKIE_MAX_AGE_SECONDS),
    }
    return jwt.encode(payload, secrets.get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_session_token(token: str | None) -> UserInfo:
    if token is None:
        raise InvalidSessionError()
    try:
        payload = jwt.decode(token, secrets.get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidSessionError() from exc
    return UserInfo(email=payload["sub"], name=payload["name"], picture=payload.get("picture"))
