"""Única camada que fala com o Firestore pra controle de acesso do Hub —
service.py orquestra, nunca monta paths/queries diretamente (mesmo
racional de domains/favorites/repository.py).

Coleção: hub_users/{email} — separada de users/{email} (namespace já usado
por favorites/history) porque a semântica é diferente: isso é controle de
acesso administrado por admins do Hub, não dado pessoal do próprio
usuário.
"""

from datetime import UTC, datetime

from google.cloud import firestore


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
