from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.auth import require_project_access
from observability_hub.core.bigquery import get_client
from observability_hub.core.logging_client import get_logging_client
from observability_hub.domains.lineage import service
from observability_hub.domains.lineage.schemas import LineageGraphResponse, OrphansResponse

router = APIRouter(
    prefix="/api/v1/lineage", tags=["lineage"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/orphans", response_model=OrphansResponse)
def get_orphans(
    project_id: str,
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
) -> OrphansResponse:
    return service.get_orphans(client, logging_client, project_id)


@router.get("/{project_id}/{dataset_id}/{table_id}", response_model=LineageGraphResponse)
def get_lineage(
    project_id: str,
    dataset_id: str,
    table_id: str,
    max_hops: int = Query(default=8, ge=1, le=15),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
) -> LineageGraphResponse:
    return service.get_table_lineage(
        client, logging_client, project_id, dataset_id, table_id, max_hops=max_hops
    )
