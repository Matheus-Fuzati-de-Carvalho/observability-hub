from fastapi import APIRouter, Depends
from google.cloud import firestore

from observability_hub.core.auth import get_current_user
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.auth.schemas import UserInfo
from observability_hub.domains.history import service
from observability_hub.domains.history.schemas import (
    HistoryResponse,
    SearchEventRequest,
    TableViewRequest,
)

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("", response_model=HistoryResponse)
def get_history(
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> HistoryResponse:
    return service.get_history(client, user.email)


@router.post("/table-view", status_code=204)
def record_table_view(
    request: TableViewRequest,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.record_table_view(
        client, user.email, request.project_id, request.dataset_id, request.table_id
    )


@router.post("/search", status_code=204)
def record_search(
    request: SearchEventRequest,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.record_search(client, user.email, request.query, request.mode, request.project_id)
