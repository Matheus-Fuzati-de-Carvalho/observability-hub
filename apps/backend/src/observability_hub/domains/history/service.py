"""Orquestra o domínio history: busca/grava via repository, monta os
schemas de response. api/v1/history.py só chama estas funções —
CLAUDE.md proíbe lógica de negócio em api/.
"""

from google.cloud import firestore

from observability_hub.domains.history import repository
from observability_hub.domains.history.schemas import HistoryResponse, SearchEvent, TableViewEvent


def get_history(client: firestore.Client, email: str) -> HistoryResponse:
    recent_tables = repository.list_recent_table_views(client, email)
    recent_searches = repository.list_recent_searches(client, email)
    return HistoryResponse(
        recent_tables=[TableViewEvent(**t) for t in recent_tables],
        recent_searches=[SearchEvent(**s) for s in recent_searches],
    )


def record_table_view(
    client: firestore.Client, email: str, project_id: str, dataset_id: str, table_id: str
) -> None:
    repository.add_table_view(client, email, project_id, dataset_id, table_id)


def record_search(
    client: firestore.Client, email: str, query: str, mode: str, project_id: str
) -> None:
    repository.add_search(client, email, query, mode, project_id)
