"""Orquestra o domínio catalog: descobre regiões via core.bigquery, busca
dados via repository, monta os schemas de response. api/v1 só chama estas
funções — CLAUDE.md proíbe lógica de negócio em api/.
"""

from datetime import UTC, datetime

from google.cloud import bigquery

from observability_hub.core.bigquery import discover_regions
from observability_hub.domains.catalog import repository
from observability_hub.domains.catalog.schemas import (
    ColumnDetail,
    DatasetsListResponse,
    DatasetSummary,
    ProjectValidateResponse,
    TableDetail,
    TablesListResponse,
    TableSummary,
)


def validate_project(client: bigquery.Client, project_id: str) -> ProjectValidateResponse:
    regions = discover_regions(project_id, client=client)
    datasets = repository.get_datasets_summary(client, project_id, regions)
    return ProjectValidateResponse(
        project_id=project_id,
        accessible=True,
        available_regions=regions,
        total_datasets=len(datasets),
        # client.project é resolvido pelo SDK via GOOGLE_CLOUD_PROJECT ou
        # google.auth.default() (metadados do Cloud Run em produção) — mesma
        # fonte já usada em main.py para montar o "fix" de ProjectAccessDeniedError.
        is_native=project_id == client.project,
    )


def list_datasets(client: bigquery.Client, project_id: str) -> DatasetsListResponse:
    regions = discover_regions(project_id, client=client)
    raw_datasets = repository.get_datasets_summary(client, project_id, regions)
    return DatasetsListResponse(
        project_id=project_id,
        evaluated_at=datetime.now(UTC),
        total_datasets=len(raw_datasets),
        regions_found=regions,
        datasets=[DatasetSummary(**d) for d in raw_datasets],
    )


def list_tables(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_type: str | None = None,
) -> TablesListResponse:
    regions = discover_regions(project_id, client=client)
    location = repository.resolve_dataset_region(client, project_id, dataset_id, regions)
    raw_tables = repository.get_tables_summary(
        client, project_id, dataset_id, location, table_type=table_type
    )
    return TablesListResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        location=location,
        total_tables=len(raw_tables),
        tables=[TableSummary(**t) for t in raw_tables],
    )


def get_table_detail(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str
) -> TableDetail:
    regions = discover_regions(project_id, client=client)
    location = repository.resolve_dataset_region(client, project_id, dataset_id, regions)
    raw_detail = repository.get_table_detail(client, project_id, dataset_id, table_id, location)
    columns = [ColumnDetail(**c) for c in raw_detail.pop("columns")]
    return TableDetail(**raw_detail, columns=columns)
