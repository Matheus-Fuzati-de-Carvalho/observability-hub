"""Única camada que fala com o Firestore pro histórico de scans de PII —
service.py orquestra, nunca monta paths/queries diretamente (mesmo
racional de domains/quality/history_repository.py, que este arquivo
espelha quase 1:1).

pii_scan_history/{project}_{dataset}_{table}/scans/{auto-id} — mesmo
padrão de trim-to-max de domains/quality/history_repository.py, mas o
nome da subcoleção é "scans", não "runs": domains/admin/
analytics_repository.py::list_all_profiling_runs já lê
collection_group("runs") pra agregar profiling entre tabelas —
collection_group ignora o caminho do documento-pai, só olha o nome da
subcoleção, então usar "runs" aqui faria os dois históricos se
misturarem na agregação global. Nomes diferentes evitam a colisão.
"""

from datetime import UTC, datetime

from google.cloud import firestore

_MAX_SCANS = 30


def _table_doc_id(project_id: str, dataset_id: str, table_id: str) -> str:
    return f"{project_id}_{dataset_id}_{table_id}"


def _scans_collection(client: firestore.Client, project_id: str, dataset_id: str, table_id: str):
    doc_id = _table_doc_id(project_id, dataset_id, table_id)
    return client.collection("pii_scan_history").document(doc_id).collection("scans")


def _trim_to_max(collection) -> None:
    overflow = (
        collection.order_by("executed_at", direction=firestore.Query.DESCENDING)
        .offset(_MAX_SCANS)
        .stream()
    )
    for doc in overflow:
        doc.reference.delete()


def save_scan(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    executed_by: str,
    flagged_columns_count: int,
    columns: list[dict],
) -> None:
    collection = _scans_collection(client, project_id, dataset_id, table_id)
    collection.add(
        {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "table_id": table_id,
            "executed_at": datetime.now(UTC),
            "executed_by": executed_by,
            "flagged_columns_count": flagged_columns_count,
            "columns": columns,
        }
    )
    _trim_to_max(collection)
