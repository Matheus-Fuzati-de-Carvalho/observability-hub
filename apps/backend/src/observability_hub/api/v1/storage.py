from fastapi import APIRouter, Depends, Query
from google.cloud import logging as cloud_logging
from google.cloud import storage

from observability_hub.core.auth import require_project_access
from observability_hub.core.logging_client import get_logging_client
from observability_hub.core.storage_client import get_storage_client
from observability_hub.domains.storage import service
from observability_hub.domains.storage.schemas import (
    BucketsListResponse,
    MinDaysUnused,
    WasteCandidatesResponse,
)

router = APIRouter(
    prefix="/api/v1/storage", tags=["storage"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/buckets", response_model=BucketsListResponse)
def list_buckets(
    project_id: str, client: storage.Client = Depends(get_storage_client)
) -> BucketsListResponse:
    return service.list_buckets(client, project_id)


@router.get("/{project_id}/waste-candidates", response_model=WasteCandidatesResponse)
def get_waste_candidates(
    project_id: str,
    min_days_unused: MinDaysUnused = Query(default=MinDaysUnused.SIXTY),
    client: storage.Client = Depends(get_storage_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
) -> WasteCandidatesResponse:
    return service.get_waste_candidates(client, logging_client, project_id, min_days_unused)
