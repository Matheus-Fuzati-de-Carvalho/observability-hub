from fastapi import APIRouter, Depends
from google.cloud import bigquery, firestore

from observability_hub.core.auth import get_current_user
from observability_hub.core.bigquery import get_client
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.quality import service
from observability_hub.domains.quality.schemas import QualityScoreResponse

router = APIRouter(
    prefix="/api/v1/quality", tags=["quality"], dependencies=[Depends(get_current_user)]
)


@router.get("/score/{project_id}/{dataset_id}/{table_id}", response_model=QualityScoreResponse)
def get_quality_score(
    project_id: str,
    dataset_id: str,
    table_id: str,
    client: bigquery.Client = Depends(get_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> QualityScoreResponse:
    return service.get_quality_score(client, firestore_client, project_id, dataset_id, table_id)
