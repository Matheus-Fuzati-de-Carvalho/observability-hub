"""Única camada que fala com o Firestore pra controle de acesso do Hub —
service.py orquestra, nunca monta paths/queries diretamente (mesmo
racional de domains/favorites/repository.py).

Três coleções:
- hub_users/{email} — separada de users/{email} (namespace já usado por
  favorites/history) porque a semântica é diferente: controle de acesso
  administrado por admins do Hub, não dado pessoal do próprio usuário.
- hub_projects/{project_id} — eixo independente de hub_users: um projeto
  marcado is_public libera geral, inclusive usuário sem doc em hub_users.
- access_requests/{auto_id} — pedidos de acesso, doc_id gerado pelo
  Firestore (não determinístico como em favorites: um usuário pode pedir
  o mesmo projeto de novo depois de negado, cada pedido é um doc à parte).
"""

from datetime import UTC, datetime

from google.cloud import firestore
from google.cloud.firestore import FieldFilter


def _users_collection(client: firestore.Client):
    return client.collection("hub_users")


def get_user(client: firestore.Client, email: str) -> dict | None:
    doc = _users_collection(client).document(email).get()
    return doc.to_dict() if doc.exists else None


def list_users(client: firestore.Client) -> list[dict]:
    docs = _users_collection(client).order_by("email").stream()
    return [doc.to_dict() for doc in docs]


def upsert_user(
    client: firestore.Client,
    email: str,
    is_admin: bool,
    allowed_projects: list[str],
    updated_by: str,
) -> dict:
    """created_at/updated_at escritos como datetime.now(UTC) direto (não o
    sentinel firestore.SERVER_TIMESTAMP) — mesmo racional de
    favorites/repository.py::add_favorite: queremos devolver o valor real
    na resposta do PUT sem round-trip extra. created_at só é definido na
    primeira gravação (preserva o valor original em updates)."""
    now = datetime.now(UTC)
    existing = get_user(client, email)
    data = {
        "email": email,
        "is_admin": is_admin,
        "allowed_projects": allowed_projects,
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
        "updated_by": updated_by,
    }
    _users_collection(client).document(email).set(data)
    return data


def delete_user(client: firestore.Client, email: str) -> None:
    _users_collection(client).document(email).delete()


def users_with_project_access(client: firestore.Client, project_id: str) -> list[dict]:
    """Usuários com este project_id OU "*" em allowed_projects — uma
    query só via array_contains_any, sem escanear a coleção inteira.
    Não inclui quem só tem acesso via hub_projects.is_public (isso é
    "todo mundo", não uma lista finita — tratado à parte em
    service.py::get_project_users)."""
    docs = (
        _users_collection(client)
        .where(filter=FieldFilter("allowed_projects", "array_contains_any", [project_id, "*"]))
        .stream()
    )
    return [doc.to_dict() for doc in docs]


def _projects_collection(client: firestore.Client):
    return client.collection("hub_projects")


def get_project(client: firestore.Client, project_id: str) -> dict | None:
    doc = _projects_collection(client).document(project_id).get()
    return doc.to_dict() if doc.exists else None


def list_projects(client: firestore.Client) -> list[dict]:
    docs = _projects_collection(client).order_by("project_id").stream()
    return [doc.to_dict() for doc in docs]


def upsert_project(
    client: firestore.Client, project_id: str, is_public: bool, updated_by: str
) -> dict:
    now = datetime.now(UTC)
    existing = get_project(client, project_id)
    data = {
        "project_id": project_id,
        "is_public": is_public,
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
        "updated_by": updated_by,
    }
    _projects_collection(client).document(project_id).set(data)
    return data


def _access_requests_collection(client: firestore.Client):
    return client.collection("access_requests")


def create_access_request(
    client: firestore.Client, email: str, project_id: str, now: datetime
) -> dict:
    """doc_id gerado pelo Firestore (.document() sem argumento) — cada
    pedido é uma entrada própria, não um upsert por email/projeto."""
    doc_ref = _access_requests_collection(client).document()
    data = {
        "request_id": doc_ref.id,
        "email": email,
        "project_id": project_id,
        "status": "pending",
        "requested_at": now,
        "resolved_at": None,
        "resolved_by": None,
    }
    doc_ref.set(data)
    return data


def list_access_requests(client: firestore.Client, status: str | None = None) -> list[dict]:
    """Filtro por status (se houver) é a única cláusula where — evita
    depender de índice composto (where + order_by em campos diferentes
    exigiria criar um manualmente no console, sem aviso em código);
    ordenação por requested_at é feita em Python, coleção pequena o
    bastante pra isso não pesar."""
    if status is not None:
        docs = _access_requests_collection(client).where(filter=FieldFilter("status", "==", status))
    else:
        docs = _access_requests_collection(client)
    results = [doc.to_dict() for doc in docs.stream()]
    results.sort(key=lambda r: r["requested_at"], reverse=True)
    return results


def has_pending_request(client: firestore.Client, email: str, project_id: str) -> bool:
    """Só um campo no where (email) — mesmo motivo de list_access_requests,
    evita índice composto de 3 campos; project_id/status filtrados em
    Python sobre os pedidos desse e-mail (poucos, por usuário)."""
    docs = _access_requests_collection(client).where(filter=FieldFilter("email", "==", email))
    return any(
        d["project_id"] == project_id and d["status"] == "pending"
        for d in (doc.to_dict() for doc in docs.stream())
    )


def get_access_request(client: firestore.Client, request_id: str) -> dict | None:
    doc = _access_requests_collection(client).document(request_id).get()
    return doc.to_dict() if doc.exists else None


def update_access_request_status(
    client: firestore.Client, request_id: str, status: str, resolved_by: str, now: datetime
) -> dict:
    doc_ref = _access_requests_collection(client).document(request_id)
    doc_ref.update({"status": status, "resolved_at": now, "resolved_by": resolved_by})
    return doc_ref.get().to_dict()
