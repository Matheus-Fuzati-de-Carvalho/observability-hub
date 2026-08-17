"""Dependências FastAPI de autenticação/autorização — aplicadas a nível
de router (via `dependencies=[Depends(...)]`) na maioria dos domínios.
Mora em core/ porque é transversal, mesmo racional de core/bigquery.py.

require_admin e require_project_access dependem de get_current_user
internamente — o FastAPI cacheia a resolução de dependency por request,
então usar as duas juntas (ex: um endpoint que declara
Depends(get_current_user) e o router já usa Depends(require_admin)) não
decodifica o JWT duas vezes.
"""

from fastapi import Cookie, Depends
from google.cloud import firestore

from observability_hub.core.exceptions import AdminAccessRequiredError, ProjectNotAuthorizedError
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.admin import service as admin_service
from observability_hub.domains.auth import service
from observability_hub.domains.auth.schemas import UserInfo


def get_current_user(
    session: str | None = Cookie(default=None, alias=service.SESSION_COOKIE_NAME),
) -> UserInfo:
    return service.decode_session_token(session)


def require_admin(
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> UserInfo:
    """Sessão válida não basta — precisa também de is_admin=True em
    hub_users/{email} (domains/admin). Leitura sempre fresca do
    Firestore, sem cache (ver domains/admin/service.py)."""
    if not admin_service.is_admin(client, user.email):
        raise AdminAccessRequiredError()
    return user


def require_project_access(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> UserInfo:
    """Aplicada no lugar de get_current_user em todo router que recebe
    project_id como path param — barra ANTES de qualquer chamada real ao
    BigQuery/Cloud Logging do projeto alvo, mesmo que a service account
    de runtime tenha IAM lá (ADR-006 é sobre a SA alcançar o projeto;
    isto aqui é sobre o USUÁRIO estar autorizado no Hub a usar esse
    acesso). Usuário sem doc em hub_users tem allowed_projects vazio,
    nega tudo por padrão (fail closed)."""
    if not admin_service.has_project_access(client, user.email, project_id):
        raise ProjectNotAuthorizedError(project_id)
    return user
