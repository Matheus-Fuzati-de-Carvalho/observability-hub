"""Única camada que fala com o Firestore pros dados de uso/gestão do
Hub (login, favoritos entre usuários, atividade de profiling, navegação
agregada, scans de PII) — service.py orquestra, nunca monta paths/
queries diretamente (mesmo racional de domains/admin/repository.py).

Coleção nova: login_events/{auto_id} — top-level, não por usuário (é
dado gerencial do Hub, mesmo raciocínio de hub_users/hub_projects, não
dado pessoal do usuário como favorites/history). Sem trim-to-max: volume
esperado é baixo (time interno, não multi-tenant ainda) — revisitar se
isso mudar.

As duas outras leituras usam collection_group SEM filtro nem order_by —
mesma disciplina de list_access_requests (evitar índice composto/de
collection-group manual): ordenação e agrupamento acontecem em Python.
"""

from datetime import datetime

from google.cloud import firestore
from google.cloud.firestore import FieldFilter


def _login_events_collection(client: firestore.Client):
    return client.collection("login_events")


def record_login(client: firestore.Client, email: str, now: datetime) -> None:
    _login_events_collection(client).add({"email": email, "logged_in_at": now})


def list_login_events(client: firestore.Client, since: datetime) -> list[dict]:
    """Único filtro (range em logged_in_at) — sem order_by combinado,
    evita índice composto. Ordenação em Python."""
    docs = _login_events_collection(client).where(filter=FieldFilter("logged_in_at", ">=", since))
    results = [doc.to_dict() for doc in docs.stream()]
    results.sort(key=lambda e: e["logged_in_at"], reverse=True)
    return results


def list_all_favorites(client: firestore.Client) -> list[dict]:
    """collection_group sem filtro — cada doc ganha owner_email, derivado
    do path (users/{email}/favorites/{doc_id}, o e-mail é o ID do
    documento-pai)."""
    docs = client.collection_group("favorites").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["owner_email"] = doc.reference.parent.parent.id
        results.append(data)
    return results


def list_all_profiling_runs(client: firestore.Client) -> list[dict]:
    docs = client.collection_group("runs").stream()
    return [doc.to_dict() for doc in docs]


def list_all_table_views(client: firestore.Client) -> list[dict]:
    """collection_group sem filtro — cada doc ganha owner_email, derivado
    do path (users/{email}/history_table_views/{doc_id}). Cada usuário só
    guarda os 20 mais recentes (domains/history/repository.py) — isso é
    uma janela recente, não histórico completo."""
    docs = client.collection_group("history_table_views").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["owner_email"] = doc.reference.parent.parent.id
        results.append(data)
    return results


def list_all_searches(client: firestore.Client) -> list[dict]:
    docs = client.collection_group("history_searches").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["owner_email"] = doc.reference.parent.parent.id
        results.append(data)
    return results


def list_all_pii_scans(client: firestore.Client) -> list[dict]:
    """Nome da subcoleção é "scans", não "runs" — ver docstring de
    domains/pii/history_repository.py sobre a colisão de
    collection_group que isso evita."""
    docs = client.collection_group("scans").stream()
    return [doc.to_dict() for doc in docs]
