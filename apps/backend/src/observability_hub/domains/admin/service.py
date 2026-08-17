"""Orquestra o domínio admin: controle de acesso do Hub por usuário
(quem é admin, quais project_id cada um pode operar). api/v1/admin.py e
core/auth.py (require_admin/require_project_access) só chamam estas
funções — CLAUDE.md proíbe lógica de negócio em api/.

Sem cache de leitura em nenhuma função aqui — leitura sempre fresca do
Firestore. O @lru_cache sem TTL de core/secrets.py::get_oauth_allowlist
já causou staleness real nesta mesma sessão (instância quente do Cloud
Run não pega mudança de acesso até reiniciar); não repetir o erro num
controle de acesso que precisa refletir revogação imediatamente.
"""

from datetime import UTC, datetime

from google.cloud import firestore

from observability_hub.core.exceptions import AccessRequestNotFoundError, LastAdminLockoutError
from observability_hub.domains.admin import repository
from observability_hub.domains.admin.schemas import (
    AccessRequest,
    AccessRequestsListResponse,
    HubProject,
    HubProjectsListResponse,
    HubUser,
    HubUsersListResponse,
    ProjectAccessGrant,
    ProjectUsersResponse,
    UpsertHubProjectRequest,
    UpsertHubUserRequest,
)

# Wildcard: libera qualquer project_id que a service account de runtime
# alcançar — ver docs/specs/admin.md.
_WILDCARD_PROJECT = "*"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _count_other_admins(users: list[dict], excluding_email: str) -> int:
    return sum(1 for u in users if u["is_admin"] and u["email"] != excluding_email)


def list_users(client: firestore.Client) -> HubUsersListResponse:
    raw = repository.list_users(client)
    return HubUsersListResponse(users=[HubUser(**u) for u in raw])


def upsert_user(
    client: firestore.Client, email: str, request: UpsertHubUserRequest, updated_by: str
) -> HubUser:
    email = _normalize_email(email)
    if not request.is_admin:
        existing = repository.get_user(client, email)
        if existing and existing.get("is_admin"):
            others = _count_other_admins(repository.list_users(client), excluding_email=email)
            if others == 0:
                raise LastAdminLockoutError(email)

    raw = repository.upsert_user(
        client, email, request.is_admin, request.allowed_projects, _normalize_email(updated_by)
    )
    return HubUser(**raw)


def delete_user(client: firestore.Client, email: str) -> None:
    email = _normalize_email(email)
    existing = repository.get_user(client, email)
    if existing and existing.get("is_admin"):
        others = _count_other_admins(repository.list_users(client), excluding_email=email)
        if others == 0:
            raise LastAdminLockoutError(email)
    repository.delete_user(client, email)


def is_admin(client: firestore.Client, email: str) -> bool:
    user = repository.get_user(client, _normalize_email(email))
    return bool(user and user.get("is_admin"))


def has_project_access(client: firestore.Client, email: str, project_id: str) -> bool:
    """hub_projects/{project_id}.is_public checado primeiro — libera
    geral, inclusive quem não tem doc em hub_users (usuário futuro).
    Senão, sem doc em hub_users -> allowed_projects vazio -> nega tudo
    (fail closed) — ver docs/specs/admin.md, "Casos de borda"."""
    project = repository.get_project(client, project_id)
    if project and project.get("is_public"):
        return True

    user = repository.get_user(client, _normalize_email(email))
    if not user:
        return False
    allowed: list[str] = user.get("allowed_projects", [])
    return _WILDCARD_PROJECT in allowed or project_id in allowed


# --- hub_projects ------------------------------------------------------------------


def list_projects(client: firestore.Client) -> HubProjectsListResponse:
    raw = repository.list_projects(client)
    return HubProjectsListResponse(projects=[HubProject(**p) for p in raw])


def upsert_project(
    client: firestore.Client, project_id: str, request: UpsertHubProjectRequest, updated_by: str
) -> HubProject:
    raw = repository.upsert_project(
        client, project_id, request.is_public, _normalize_email(updated_by)
    )
    return HubProject(**raw)


def get_project_users(client: firestore.Client, project_id: str) -> ProjectUsersResponse:
    project = repository.get_project(client, project_id)
    is_public = bool(project and project.get("is_public"))

    raw_users = repository.users_with_project_access(client, project_id)
    grants = [
        ProjectAccessGrant(
            email=u["email"],
            is_admin=u["is_admin"],
            granted_via="wildcard"
            if _WILDCARD_PROJECT in u.get("allowed_projects", [])
            else "explicit",
        )
        for u in raw_users
    ]
    return ProjectUsersResponse(project_id=project_id, is_public=is_public, users=grants)


def grant_project_to_user(
    client: firestore.Client, project_id: str, email: str, updated_by: str
) -> HubUser:
    """Cria o usuário (is_admin=False) se ainda não existir. Preserva o
    resto da lista de allowed_projects — só adiciona project_id se ainda
    não estiver lá (idempotente)."""
    email = _normalize_email(email)
    existing = repository.get_user(client, email)
    is_admin_flag = bool(existing["is_admin"]) if existing else False
    allowed = list(existing["allowed_projects"]) if existing else []
    if project_id not in allowed:
        allowed.append(project_id)
    raw = repository.upsert_user(
        client, email, is_admin_flag, allowed, _normalize_email(updated_by)
    )
    return HubUser(**raw)


def revoke_project_from_user(
    client: firestore.Client, project_id: str, email: str, updated_by: str
) -> HubUser | None:
    """None se o usuário não tinha doc (nada a revogar). Diferente de
    upsert_user/delete_user: revogar um PROJETO nunca é bloqueado por
    LastAdminLockoutError — isso só se aplica a remover status de admin,
    não acesso a projeto."""
    email = _normalize_email(email)
    existing = repository.get_user(client, email)
    if existing is None:
        return None
    allowed = [p for p in existing["allowed_projects"] if p != project_id]
    raw = repository.upsert_user(
        client, email, existing["is_admin"], allowed, _normalize_email(updated_by)
    )
    return HubUser(**raw)


# --- access_requests -----------------------------------------------------------------


def create_access_requests(
    client: firestore.Client, email: str, project_ids: list[str]
) -> AccessRequestsListResponse:
    """Pula project_id que o usuário já tem acesso (has_project_access)
    e project_id com pedido pending já existente do mesmo usuário —
    nunca cria pedido redundante."""
    email = _normalize_email(email)
    now = datetime.now(UTC)
    created: list[dict] = []
    for project_id in project_ids:
        if has_project_access(client, email, project_id):
            continue
        if repository.has_pending_request(client, email, project_id):
            continue
        created.append(repository.create_access_request(client, email, project_id, now))
    return AccessRequestsListResponse(requests=[AccessRequest(**r) for r in created])


def list_access_requests(
    client: firestore.Client, status: str | None = None
) -> AccessRequestsListResponse:
    raw = repository.list_access_requests(client, status)
    return AccessRequestsListResponse(requests=[AccessRequest(**r) for r in raw])


def _resolve_access_request(
    client: firestore.Client, request_id: str, status: str, resolved_by: str
) -> AccessRequest:
    existing = repository.get_access_request(client, request_id)
    if existing is None:
        raise AccessRequestNotFoundError(request_id)

    if status == "approved":
        grant_project_to_user(client, existing["project_id"], existing["email"], resolved_by)

    raw = repository.update_access_request_status(
        client, request_id, status, _normalize_email(resolved_by), datetime.now(UTC)
    )
    return AccessRequest(**raw)


def approve_access_request(
    client: firestore.Client, request_id: str, resolved_by: str
) -> AccessRequest:
    return _resolve_access_request(client, request_id, "approved", resolved_by)


def deny_access_request(
    client: firestore.Client, request_id: str, resolved_by: str
) -> AccessRequest:
    return _resolve_access_request(client, request_id, "denied", resolved_by)
