"""Dependência FastAPI de autenticação — aplicada a nível de router (via
`dependencies=[Depends(get_current_user)]`) em todos os domínios que
expõem dados (catalog, freshness, profiling, projects, favorites,
history), não só nos endpoints do próprio domínio auth. Mora em core/
porque é transversal, mesmo racional de core/bigquery.py.
"""

from fastapi import Cookie

from observability_hub.domains.auth import service
from observability_hub.domains.auth.schemas import UserInfo


def get_current_user(
    session: str | None = Cookie(default=None, alias=service.SESSION_COOKIE_NAME),
) -> UserInfo:
    return service.decode_session_token(session)
