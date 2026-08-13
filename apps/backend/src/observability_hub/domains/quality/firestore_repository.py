"""Única camada que fala com o Firestore no domínio quality — service.py
orquestra, nunca monta paths diretamente (mesmo racional de
domains/favorites e domains/history). Separado de repository.py porque
esse é exclusivamente BigQuery (ver seu próprio docstring) — misturar as
duas fontes no mesmo arquivo confundiria o propósito de cada uma.

Coleção compartilhada (não por usuário) — profiling_results/
{project}_{dataset}_{table}, um doc só por tabela, sobrescrito a cada
run. Compartilhada (não users/{email}/...) por decisão consciente: o
score de qualidade (domains/quality/score.py) precisa significar a mesma
coisa pra qualquer usuário que olhe a tabela, não depender de quem
rodou o último profiling.
"""

from datetime import UTC, datetime

from google.cloud import firestore


def _profiling_result_doc_id(project_id: str, dataset_id: str, table_id: str) -> str:
    return f"{project_id}_{dataset_id}_{table_id}"


def _profiling_results_collection(client: firestore.Client):
    return client.collection("profiling_results")


def get_last_profiling_result(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> dict | None:
    doc_id = _profiling_result_doc_id(project_id, dataset_id, table_id)
    snapshot = _profiling_results_collection(client).document(doc_id).get()
    return snapshot.to_dict() if snapshot.exists else None


def save_profiling_result(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    overall_density: float,
    estimated_duplicate_pct: float,
    executed_by: str,
) -> None:
    doc_id = _profiling_result_doc_id(project_id, dataset_id, table_id)
    _profiling_results_collection(client).document(doc_id).set(
        {
            "overall_density": overall_density,
            "estimated_duplicate_pct": estimated_duplicate_pct,
            "executed_at": datetime.now(UTC),
            "executed_by": executed_by,
        }
    )
