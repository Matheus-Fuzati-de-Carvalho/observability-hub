from fastapi import APIRouter, Depends
from google.cloud import storage

from observability_hub.core.auth import require_project_access
from observability_hub.core.storage_client import get_storage_client
from observability_hub.domains.storage import service
from observability_hub.domains.storage.schemas import BucketFreshnessResponse, BucketsListResponse

router = APIRouter(
    prefix="/api/v1/storage", tags=["storage"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/buckets", response_model=BucketsListResponse)
def list_buckets(
    project_id: str, client: storage.Client = Depends(get_storage_client)
) -> BucketsListResponse:
    return service.list_buckets(client, project_id)


@router.get("/{project_id}/buckets/{bucket_name}/freshness", response_model=BucketFreshnessResponse)
def get_bucket_freshness(
    project_id: str, bucket_name: str, client: storage.Client = Depends(get_storage_client)
) -> BucketFreshnessResponse:
    return service.get_bucket_freshness(client, bucket_name)
