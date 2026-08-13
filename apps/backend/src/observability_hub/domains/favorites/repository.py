"""Única camada que fala com o Firestore pra favoritos — service.py
orquestra, nunca monta paths/queries diretamente (mesmo racional dos
demais domínios).

Coleção: users/{email}/favorites/{doc_id}. doc_id é determinístico
(project_id__dataset_id__table_id, "__" pra reduzir colisão com "_" que
já aparece normalmente em nomes de dataset/tabela) — favoritar a mesma
tabela duas vezes é idempotente (mesmo doc, só sobrescreve added_at) e
DELETE consegue apontar pro doc exato sem precisar de query.
"""

from datetime import UTC, datetime

from google.cloud import firestore


def _favorite_doc_id(project_id: str, dataset_id: str, table_id: str) -> str:
    return f"{project_id}__{dataset_id}__{table_id}"


def _favorites_collection(client: firestore.Client, email: str):
    return client.collection("users").document(email).collection("favorites")


def list_favorites(client: firestore.Client, email: str) -> list[dict]:
    docs = (
        _favorites_collection(client, email)
        .order_by("added_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [doc.to_dict() for doc in docs]


def add_favorite(
    client: firestore.Client, email: str, project_id: str, dataset_id: str, table_id: str
) -> dict:
    """added_at é escrito como datetime.now(UTC) em vez do sentinel
    firestore.SERVER_TIMESTAMP — o sentinel só resolve pro valor real
    depois de um novo GET, e queremos devolver o favorito criado direto
    na resposta do POST sem round-trip extra."""
    data = {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "table_id": table_id,
        "added_at": datetime.now(UTC),
    }
    doc_id = _favorite_doc_id(project_id, dataset_id, table_id)
    _favorites_collection(client, email).document(doc_id).set(data)
    return data


def remove_favorite(
    client: firestore.Client, email: str, project_id: str, dataset_id: str, table_id: str
) -> None:
    doc_id = _favorite_doc_id(project_id, dataset_id, table_id)
    _favorites_collection(client, email).document(doc_id).delete()
