from fastapi import APIRouter, Depends
from google.cloud import bigquery, firestore

from observability_hub.core.auth import get_current_user, require_project_access
from observability_hub.core.bigquery import get_client
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.auth.schemas import UserInfo
from observability_hub.domains.pii import service
from observability_hub.domains.pii.schemas import (
    PiiEstimateResponse,
    PiiScanRequest,
    PiiScanResponse,
)

router = APIRouter(
    prefix="/api/v1/pii", tags=["pii"], dependencies=[Depends(require_project_access)]
)


@router.post(
    "/{project_id}/{dataset_id}/{table_id}/estimate",
    response_model=PiiEstimateResponse,
)
def estimate(
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: PiiScanRequest,
    client: bigquery.Client = Depends(get_client),
) -> PiiEstimateResponse:
    return service.estimate_pii_scan(client, project_id, dataset_id, table_id, request)


@router.post(
    "/{project_id}/{dataset_id}/{table_id}/run",
    response_model=PiiScanResponse,
)
def run(
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: PiiScanRequest,
    client: bigquery.Client = Depends(get_client),
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> PiiScanResponse:
    return service.run_pii_scan(
        client, firestore_client, project_id, dataset_id, table_id, request, user.email
    )
