from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.auth import require_project_access
from observability_hub.core.bigquery import get_client
from observability_hub.core.logging_client import get_logging_client
from observability_hub.domains.finops import service
from observability_hub.domains.finops.schemas import (
    BudgetGroupBy,
    BudgetResponse,
    ColumnTypeEstimateResponse,
    ColumnTypeScanRequest,
    ColumnTypeSuggestionsResponse,
    MinDaysUnused,
    PartitionCandidatesResponse,
    UnusedTablesResponse,
)

router = APIRouter(
    prefix="/api/v1/finops", tags=["finops"], dependencies=[Depends(require_project_access)]
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


@router.get("/{project_id}/budget", response_model=BudgetResponse)
def get_budget(
    project_id: str,
    group_by: BudgetGroupBy = Query(default=BudgetGroupBy.TABLE),
    limit: int = Query(default=10, ge=1, le=50),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
) -> BudgetResponse:
    return service.get_budget(logging_client, project_id, group_by=group_by, limit=limit)


@router.post(
    "/{project_id}/column-type-suggestions/estimate", response_model=ColumnTypeEstimateResponse
)
def estimate_column_type_suggestions(
    project_id: str,
    request: ColumnTypeScanRequest,
    client: bigquery.Client = Depends(get_client),
) -> ColumnTypeEstimateResponse:
    return service.estimate_column_type_suggestions(client, project_id, request)


@router.post(
    "/{project_id}/column-type-suggestions/run", response_model=ColumnTypeSuggestionsResponse
)
def run_column_type_suggestions(
    project_id: str,
    request: ColumnTypeScanRequest,
    client: bigquery.Client = Depends(get_client),
) -> ColumnTypeSuggestionsResponse:
    return service.run_column_type_suggestions(client, project_id, request)
