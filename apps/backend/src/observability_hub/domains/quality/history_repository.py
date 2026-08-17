"""Única camada que fala com o Firestore pro histórico de profiling —
service.py orquestra, nunca monta paths/queries diretamente (mesmo
racional de domains/history e do antigo domains/quality/firestore_
repository.py). Coleção compartilhada (não por usuário) — mesma decisão
consciente já tomada pro score (removido): o histórico de uma tabela não
deve depender de quem rodou cada profiling.

profiling_history/{project}_{dataset}_{table}/runs/{auto-id} — uma
subcoleção "runs" por tabela, mesmo padrão de trim-to-max de
domains/history/repository.py (order_by + offset + delete do excedente),
só que aqui o limite é 30 em vez de 20.

Cada run também grava project_id/dataset_id/table_id (redundante com o ID
do doc-pai, que usa "_" como separador e por isso não dá pra parsear de
volta com segurança) — existe só pra domains/admin/analytics_repository.py
poder rodar um collection_group("runs") global sem precisar decompor o
ID do documento-pai.
"""

from datetime import UTC, datetime

from google.cloud import firestore

_MAX_RUNS = 30


def _table_doc_id(project_id: str, dataset_id: str, table_id: str) -> str:
    return f"{project_id}_{dataset_id}_{table_id}"


def _runs_collection(client: firestore.Client, project_id: str, dataset_id: str, table_id: str):
    doc_id = _table_doc_id(project_id, dataset_id, table_id)
    return client.collection("profiling_history").document(doc_id).collection("runs")


def _trim_to_max(collection) -> None:
    overflow = (
        collection.order_by("executed_at", direction=firestore.Query.DESCENDING)
        .offset(_MAX_RUNS)
        .stream()
    )
    for doc in overflow:
        doc.reference.delete()


def save_run(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    overall_density: float,
    estimated_duplicate_pct: float,
    executed_by: str,
    columns: list[dict],
) -> None:
    collection = _runs_collection(client, project_id, dataset_id, table_id)
    collection.add(
        {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "table_id": table_id,
            "executed_at": datetime.now(UTC),
            "executed_by": executed_by,
            "overall_density": overall_density,
            "estimated_duplicate_pct": estimated_duplicate_pct,
            "columns": columns,
        }
    )
    _trim_to_max(collection)


def list_runs(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> list[dict]:
    """Mais recente primeiro — mesma ordem de domains/history. Quem
    quiser cronológico (pro gráfico) inverte no consumidor."""
    docs = (
        _runs_collection(client, project_id, dataset_id, table_id)
        .order_by("executed_at", direction=firestore.Query.DESCENDING)
        .limit(_MAX_RUNS)
        .stream()
    )
    return [doc.to_dict() for doc in docs]
