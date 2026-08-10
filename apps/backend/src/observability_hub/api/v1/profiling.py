from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery

from observability_hub.core.bigquery import get_client
from observability_hub.domains.quality import service
from observability_hub.domains.quality.schemas import (
    EstimateResponse,
    Granularity,
    NullDistributionResponse,
    ProfilingRequest,
    ProfilingRunResponse,
)

router = APIRouter(prefix="/api/v1/profiling", tags=["profiling"])


@router.post(
    "/{project_id}/{dataset_id}/{table_id}/estimate",
    response_model=EstimateResponse,
)
def estimate(
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: ProfilingRequest,
    client: bigquery.Client = Depends(get_client),
) -> EstimateResponse:
    return service.estimate_profiling(client, project_id, dataset_id, table_id, request)


@router.post(
    "/{project_id}/{dataset_id}/{table_id}/run",
    response_model=ProfilingRunResponse,
)
def run(
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: ProfilingRequest,
    client: bigquery.Client = Depends(get_client),
) -> ProfilingRunResponse:
    return service.run_profiling(client, project_id, dataset_id, table_id, request)


@router.get(
    "/{project_id}/{dataset_id}/{table_id}/null-distribution",
    response_model=NullDistributionResponse,
)
def null_distribution(
    project_id: str,
    dataset_id: str,
    table_id: str,
    column_name: str = Query(...),
    date_column: str = Query(...),
    date_window_days: int = Query(default=30),
    granularity: Granularity = Query(default=Granularity.DAY),
    client: bigquery.Client = Depends(get_client),
) -> NullDistributionResponse:
    return service.get_null_distribution(
        client,
        project_id,
        dataset_id,
        table_id,
        column_name,
        date_column,
        date_window_days,
        granularity,
    )
