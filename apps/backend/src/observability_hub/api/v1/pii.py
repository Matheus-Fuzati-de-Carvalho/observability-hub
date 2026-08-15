from fastapi import APIRouter, Depends
from google.cloud import bigquery

from observability_hub.core.auth import get_current_user
from observability_hub.core.bigquery import get_client
from observability_hub.domains.pii import service
from observability_hub.domains.pii.schemas import (
    PiiEstimateResponse,
    PiiScanRequest,
    PiiScanResponse,
)

router = APIRouter(prefix="/api/v1/pii", tags=["pii"], dependencies=[Depends(get_current_user)])


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
) -> PiiScanResponse:
    return service.run_pii_scan(client, project_id, dataset_id, table_id, request)
