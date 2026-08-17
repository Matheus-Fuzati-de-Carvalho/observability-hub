from fastapi import APIRouter, Depends
from google.cloud import bigquery

from observability_hub.core.auth import require_project_access
from observability_hub.core.bigquery import get_client
from observability_hub.domains.freshness import service
from observability_hub.domains.freshness.schemas import (
    FreshnessDatasetResponse,
    FreshnessProjectResponse,
)

router = APIRouter(
    prefix="/api/v1/freshness", tags=["freshness"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}", response_model=FreshnessProjectResponse)
def get_project_freshness(
    project_id: str, client: bigquery.Client = Depends(get_client)
) -> FreshnessProjectResponse:
    return service.get_project_freshness(client, project_id)


@router.get(
    "/{project_id}/datasets/{dataset_id}",
    response_model=FreshnessDatasetResponse,
)
def get_dataset_freshness(
    project_id: str,
    dataset_id: str,
    client: bigquery.Client = Depends(get_client),
) -> FreshnessDatasetResponse:
    return service.get_dataset_freshness(client, project_id, dataset_id)
