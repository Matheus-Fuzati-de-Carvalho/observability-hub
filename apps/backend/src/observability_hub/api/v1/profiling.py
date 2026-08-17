from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery, firestore

from observability_hub.core.auth import get_current_user, require_project_access
from observability_hub.core.bigquery import get_client
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.auth.schemas import UserInfo
from observability_hub.domains.quality import service
from observability_hub.domains.quality.schemas import (
    EstimateResponse,
    Granularity,
    NullDistributionResponse,
    ProfilingRequest,
    ProfilingRunResponse,
)

router = APIRouter(
    prefix="/api/v1/profiling", tags=["profiling"], dependencies=[Depends(require_project_access)]
)


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
    firestore_client: firestore.Client = Depends(get_firestore_client),
    user: UserInfo = Depends(get_current_user),
) -> ProfilingRunResponse:
    return service.run_profiling(
        client, firestore_client, project_id, dataset_id, table_id, request, user.email
    )


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
