from fastapi import APIRouter, Depends
from google.cloud import firestore

from observability_hub.core.auth import get_current_user
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.quality import service
from observability_hub.domains.quality.schemas import ProfilingHistoryResponse

router = APIRouter(
    prefix="/api/v1/quality", tags=["quality"], dependencies=[Depends(get_current_user)]
)


@router.get(
    "/history/{project_id}/{dataset_id}/{table_id}", response_model=ProfilingHistoryResponse
)
def get_history(
    project_id: str,
    dataset_id: str,
    table_id: str,
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingHistoryResponse:
    return service.get_quality_history(firestore_client, project_id, dataset_id, table_id)
