"""Única camada que fala com o Firestore pra favoritos — service.py
orquestra, nunca monta paths/queries diretamente (mesmo racional dos
demais domínios).

Coleção: users/{email}/favorites/{doc_id}. doc_id é determinístico
(project_id__dataset_id[__table_id], "__" pra reduzir colisão com "_"
que já aparece normalmente em nomes de dataset/tabela) — favoritar o
mesmo alvo duas vezes é idempotente (mesmo doc) e DELETE consegue
apontar pro doc exato sem precisar de query. table_id ausente = favorito
do dataset inteiro, doc_id com dois segmentos em vez de três.
"""

from datetime import UTC, datetime

from google.cloud import firestore


def _favorite_doc_id(project_id: str, dataset_id: str, table_id: str | None = None) -> str:
    if table_id is None:
        return f"{project_id}__{dataset_id}"
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
    client: firestore.Client,
    email: str,
    project_id: str,
    dataset_id: str,
    table_id: str | None = None,
    nickname: str | None = None,
) -> dict:
    """added_at é escrito como datetime.now(UTC) em vez do sentinel
    firestore.SERVER_TIMESTAMP — o sentinel só resolve pro valor real
    depois de um novo GET, e queremos devolver o favorito criado direto
    na resposta do POST sem round-trip extra.

    added_at é PRESERVADO em upsert repetido do mesmo alvo (mesmo
    racional de domains/admin/repository.py::upsert_user pra
    created_at) — sem isso, editar só o apelido de um favorito
    existente reordenaria a lista (ordenada por added_at desc), efeito
    colateral indesejado de uma ação que devia ser só renomear.

    nickname tem três estados na chamada, não dois: None = não mexe no
    apelido já salvo (toggle de favorito on/off nunca passa nickname, e
    não deve apagar um apelido existente); "" (string vazia) = remove o
    apelido de propósito; qualquer outra string = define o apelido."""
    doc_id = _favorite_doc_id(project_id, dataset_id, table_id)
    doc_ref = _favorites_collection(client, email).document(doc_id)
    existing = doc_ref.get()
    existing_data = existing.to_dict() if existing.exists else None
    added_at = existing_data["added_at"] if existing_data else datetime.now(UTC)

    if nickname is None:
        resolved_nickname = existing_data.get("nickname") if existing_data else None
    elif nickname == "":
        resolved_nickname = None
    else:
        resolved_nickname = nickname

    data = {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "table_id": table_id,
        "nickname": resolved_nickname,
        "added_at": added_at,
    }
    doc_ref.set(data)
    return data


def remove_favorite(
    client: firestore.Client,
    email: str,
    project_id: str,
    dataset_id: str,
    table_id: str | None = None,
) -> None:
    doc_id = _favorite_doc_id(project_id, dataset_id, table_id)
    _favorites_collection(client, email).document(doc_id).delete()
