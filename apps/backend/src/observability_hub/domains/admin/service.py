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

from google.cloud import firestore

from observability_hub.core.exceptions import LastAdminLockoutError
from observability_hub.domains.admin import repository
from observability_hub.domains.admin.schemas import (
    HubUser,
    HubUsersListResponse,
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
    """Sem doc em hub_users -> allowed_projects vazio -> nega tudo (fail
    closed) — ver docs/specs/admin.md, "Casos de borda"."""
    user = repository.get_user(client, _normalize_email(email))
    if not user:
        return False
    allowed: list[str] = user.get("allowed_projects", [])
    return _WILDCARD_PROJECT in allowed or project_id in allowed
