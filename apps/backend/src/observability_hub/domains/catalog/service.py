"""Orquestra o domínio catalog: descobre regiões via core.bigquery, busca
dados via repository, monta os schemas de response. api/v1 só chama estas
funções — CLAUDE.md proíbe lógica de negócio em api/.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from google.cloud import bigquery

from observability_hub.core.bigquery import discover_regions, get_tables_metadata
from observability_hub.core.exceptions import TableNotFoundError, TableNotPartitionedError
from observability_hub.domains.catalog import repository
from observability_hub.domains.catalog.schemas import (
    ColumnDetail,
    DatasetsListResponse,
    DatasetSummary,
    DatasetWithMatch,
    DatasetWithoutMatch,
    PartitionRow,
    ProjectValidateResponse,
    TableDetail,
    TablePartitionsResponse,
    TableSearchResponse,
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


def _fill_partition_stats(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    raw_tables: list[dict],
) -> None:
    """Busca min/max/contagem de partição em paralelo (uma chamada por
    tabela particionada, não por todas as tabelas do dataset) e mescla o
    resultado nos dicts de raw_tables in-place. partition_column já veio de
    get_tables_summary (COLUMNS.is_partitioning_column) — funciona em
    qualquer região, ao contrário de INFORMATION_SCHEMA.PARTITIONS."""
    partitioned = [t for t in raw_tables if t["is_partitioned"]]
    if not partitioned:
        return

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(
                repository.get_partition_stats,
                client,
                project_id,
                dataset_id,
                table["table_id"],
                table["partition_column"],
            ): table
            for table in partitioned
        }
        for future in as_completed(futures):
            futures[future].update(future.result())


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
    _fill_partition_stats(client, project_id, dataset_id, raw_tables)
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


def get_table_partitions(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str
) -> TablePartitionsResponse:
    """Reaproveita get_tables_summary (mesmo padrão de get_table_detail) só
    pra achar partition_column/partition_type da tabela — a listagem de
    partições em si é uma query separada, direto na tabela."""
    regions = discover_regions(project_id, client=client)
    location = repository.resolve_dataset_region(client, project_id, dataset_id, regions)
    tables = repository.get_tables_summary(client, project_id, dataset_id, location)
    table = next((t for t in tables if t["table_id"] == table_id), None)
    if table is None:
        raise TableNotFoundError(project_id, dataset_id, table_id)
    if not table["is_partitioned"]:
        raise TableNotPartitionedError(project_id, dataset_id, table_id)

    raw_partitions = repository.get_table_partitions(
        client, project_id, dataset_id, table_id, table["partition_column"]
    )
    return TablePartitionsResponse(
        table_id=table_id,
        partition_column=table["partition_column"],
        partition_type=table["partition_type"] or table["partition_column"],
        total_partitions=len(raw_partitions),
        partitions=[PartitionRow(**p) for p in raw_partitions],
    )


def search_tables(
    client: bigquery.Client, project_id: str, query: str, mode: str
) -> TableSearchResponse:
    """Busca reversa tabela → datasets: em quais datasets do projeto existe
    (ou não) uma tabela com esse nome. datasets_without_match só lista
    datasets que têm outra tabela da mesma série (mesmo prefixo sem o
    sufixo numérico final de query, ver repository.derive_search_prefix) —
    não lista todo dataset do projeto que simplesmente não bateu."""
    regions = discover_regions(project_id, client=client)
    raw_matches = repository.search_tables(client, project_id, regions, query, mode)

    table_refs = [f"{project_id}.{m['dataset_id']}.{m['table_id']}" for m in raw_matches]
    metadata_by_ref = get_tables_metadata(client, table_refs)

    def _last_modified(match: dict) -> datetime | None:
        table_ref = f"{project_id}.{match['dataset_id']}.{match['table_id']}"
        bq_table = metadata_by_ref.get(table_ref)
        return bq_table.modified if bq_table is not None else None

    datasets_with_match = [
        DatasetWithMatch(
            dataset_id=m["dataset_id"],
            table_id=m["table_id"],
            table_type=m["table_type"],
            last_modified_time=_last_modified(m),
        )
        for m in raw_matches
    ]

    datasets_without_match: list[DatasetWithoutMatch] = []
    prefix = repository.derive_search_prefix(query)
    if prefix:
        matched_dataset_ids = {m["dataset_id"] for m in raw_matches}
        prefix_rows = repository.search_tables_by_prefix(
            client, project_id, regions, prefix, matched_dataset_ids
        )
        datasets_without_match = [
            DatasetWithoutMatch(
                dataset_id=row["dataset_id"],
                reason="prefix_exists",
                latest_partition=row["latest_table"],
            )
            for row in prefix_rows
        ]

    return TableSearchResponse(
        query=query,
        mode=mode,
        project_id=project_id,
        datasets_with_match=datasets_with_match,
        datasets_without_match=datasets_without_match,
    )
