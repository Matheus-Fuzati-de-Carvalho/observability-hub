"""Única camada que fala com o Firestore pra histórico — service.py
orquestra, nunca monta paths/queries diretamente (mesmo racional dos
demais domínios).

Duas subcoleções por usuário — users/{email}/history_table_views e
users/{email}/history_searches — em vez de uma única "history" com um
campo `type` discriminando o evento (que seria mais fiel à ideia de "uma
coleção, dois tipos de evento", mas exigiria um índice composto pra
`where(type == ...).order_by(timestamp)`, já que o Firestore só indexa
automaticamente queries de campo único; equality filter + order_by em
campo diferente não é coberto pela indexação automática). Cada
subcoleção aqui só tem um tipo de documento, então `order_by(timestamp)`
sozinho já usa o índice de campo único criado automaticamente — sem
depender de nenhum índice provisionado manualmente.
"""

from datetime import UTC, datetime

from google.cloud import firestore

_MAX_ITEMS_PER_TYPE = 20


def _table_views_collection(client: firestore.Client, email: str):
    return client.collection("users").document(email).collection("history_table_views")


def _searches_collection(client: firestore.Client, email: str):
    return client.collection("users").document(email).collection("history_searches")


def _trim_to_max(collection, order_field: str) -> None:
    """Mantém só os _MAX_ITEMS_PER_TYPE mais recentes — o que sobra além
    do limite (já em ordem decrescente) é apagado."""
    overflow = (
        collection.order_by(order_field, direction=firestore.Query.DESCENDING)
        .offset(_MAX_ITEMS_PER_TYPE)
        .stream()
    )
    for doc in overflow:
        doc.reference.delete()


def add_table_view(
    client: firestore.Client, email: str, project_id: str, dataset_id: str, table_id: str
) -> None:
    collection = _table_views_collection(client, email)
    collection.add(
        {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "table_id": table_id,
            "viewed_at": datetime.now(UTC),
        }
    )
    _trim_to_max(collection, "viewed_at")


def add_search(
    client: firestore.Client, email: str, query: str, mode: str, project_id: str
) -> None:
    collection = _searches_collection(client, email)
    collection.add(
        {
            "query": query,
            "mode": mode,
            "project_id": project_id,
            "searched_at": datetime.now(UTC),
        }
    )
    _trim_to_max(collection, "searched_at")


def list_recent_table_views(client: firestore.Client, email: str) -> list[dict]:
    docs = (
        _table_views_collection(client, email)
        .order_by("viewed_at", direction=firestore.Query.DESCENDING)
        .limit(_MAX_ITEMS_PER_TYPE)
        .stream()
    )
    return [doc.to_dict() for doc in docs]


def list_recent_searches(client: firestore.Client, email: str) -> list[dict]:
    docs = (
        _searches_collection(client, email)
        .order_by("searched_at", direction=firestore.Query.DESCENDING)
        .limit(_MAX_ITEMS_PER_TYPE)
        .stream()
    )
    return [doc.to_dict() for doc in docs]
