from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery

from observability_hub.core.auth import require_project_access
from observability_hub.core.bigquery import get_client
from observability_hub.domains.catalog import service
from observability_hub.domains.catalog.schemas import (
    DatasetsListResponse,
    SearchMode,
    TableDetail,
    TablePartitionsResponse,
    TableSearchResponse,
    TablesListResponse,
    TableType,
)

router = APIRouter(
    prefix="/api/v1/catalog", tags=["catalog"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/datasets", response_model=DatasetsListResponse)
def list_datasets(
    project_id: str, client: bigquery.Client = Depends(get_client)
) -> DatasetsListResponse:
    return service.list_datasets(client, project_id)


@router.get("/{project_id}/datasets/{dataset_id}/tables", response_model=TablesListResponse)
def list_tables(
    project_id: str,
    dataset_id: str,
    table_type: TableType | None = Query(default=None),
    client: bigquery.Client = Depends(get_client),
) -> TablesListResponse:
    return service.list_tables(
        client,
        project_id,
        dataset_id,
        table_type=table_type.value if table_type else None,
    )


@router.get(
    "/{project_id}/datasets/{dataset_id}/tables/{table_id}",
    response_model=TableDetail,
)
def get_table_detail(
    project_id: str,
    dataset_id: str,
    table_id: str,
    client: bigquery.Client = Depends(get_client),
) -> TableDetail:
    return service.get_table_detail(client, project_id, dataset_id, table_id)


@router.get(
    "/{project_id}/datasets/{dataset_id}/tables/{table_id}/partitions",
    response_model=TablePartitionsResponse,
)
def get_table_partitions(
    project_id: str,
    dataset_id: str,
    table_id: str,
    client: bigquery.Client = Depends(get_client),
) -> TablePartitionsResponse:
    return service.get_table_partitions(client, project_id, dataset_id, table_id)


@router.get("/{project_id}/search", response_model=TableSearchResponse)
def search_tables(
    project_id: str,
    q: str = Query(min_length=1),
    mode: SearchMode = Query(default=SearchMode.EXACT),
    client: bigquery.Client = Depends(get_client),
) -> TableSearchResponse:
    return service.search_tables(client, project_id, q, mode.value)
