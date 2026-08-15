from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.auth import get_current_user
from observability_hub.core.bigquery import get_client
from observability_hub.core.logging_client import get_logging_client
from observability_hub.domains.finops import service
from observability_hub.domains.finops.schemas import (
    MinDaysUnused,
    PartitionCandidatesResponse,
    UnusedTablesResponse,
)

router = APIRouter(
    prefix="/api/v1/finops", tags=["finops"], dependencies=[Depends(get_current_user)]
)


@router.get("/{project_id}/unused-tables", response_model=UnusedTablesResponse)
def get_unused_tables(
    project_id: str,
    min_days_unused: MinDaysUnused = Query(default=30),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
) -> UnusedTablesResponse:
    return service.scan_unused_tables(
        client, logging_client, project_id, min_days_unused=min_days_unused
    )


@router.get("/{project_id}/partition-candidates", response_model=PartitionCandidatesResponse)
def get_partition_candidates(
    project_id: str,
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
) -> PartitionCandidatesResponse:
    return service.scan_partition_candidates(client, logging_client, project_id)
