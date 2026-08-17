from fastapi import APIRouter, Depends
from google.cloud import bigquery

from observability_hub.core.auth import require_project_access
from observability_hub.core.bigquery import get_client
from observability_hub.domains.catalog import service
from observability_hub.domains.catalog.schemas import ProjectValidateResponse

router = APIRouter(
    prefix="/api/v1/projects", tags=["projects"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/validate", response_model=ProjectValidateResponse)
def validate_project(
    project_id: str, client: bigquery.Client = Depends(get_client)
) -> ProjectValidateResponse:
    return service.validate_project(client, project_id)
