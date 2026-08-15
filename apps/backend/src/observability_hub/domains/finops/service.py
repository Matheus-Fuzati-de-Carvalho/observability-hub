"""Orquestra o domínio finops (scanner de desperdício): combina
enumeração de tabelas (BigQuery INFORMATION_SCHEMA + client.get_table()
via core/bigquery.py) com audit logs de jobs (Cloud Logging, via
repository) pra achar tabelas sem uso e candidatas a particionamento.
api/v1 só chama estas funções — CLAUDE.md proíbe lógica de negócio em
api/.
"""

from datetime import UTC, datetime

from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.bigquery import (
    discover_regions,
    get_tables_metadata,
    resolve_dataset_region,
)
from observability_hub.core.config import settings
from observability_hub.domains.finops import repository
from observability_hub.domains.finops.schemas import (
    MinDaysUnused,
    PartitionCandidate,
    PartitionCandidatesResponse,
    UnusedTable,
    UnusedTablesResponse,
)

_UNUSED_TABLES_LOOKBACK_DAYS = 90
_PARTITION_CANDIDATE_LOOKBACK_DAYS = 30
_LONG_TERM_STORAGE_THRESHOLD_DAYS = 90
_MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE = 1_073_741_824  # 1 GB
_CONSERVATIVE_REDUCTION = 0.30
_OPTIMISTIC_REDUCTION = 0.70

_EMPTY_RESULT_WARNING = (
    "Nenhum evento de job encontrado nos audit logs dos últimos {days} dias. "
    "Isso pode significar (a) que não houve atividade na janela, (b) que os "
    "Data Access audit logs estão desabilitados no projeto '{project_id}' "
    "ou (c) que a service account do Hub tem roles/logging.viewer mas não "
    "roles/logging.privateLogViewer no projeto. Verifique auditConfigs com: "
    "gcloud projects get-iam-policy {project_id} --format=json."
)

_RETENTION_CAVEAT = (
    "Data Access audit logs no Cloud Logging têm retenção padrão de 30 "
    "dias, salvo bucket/sink customizado configurado no projeto. Se esse "
    "for o caso aqui, tabelas realmente acessadas há mais de 30 dias (mas "
    "dentro da janela de {min_days_unused} dias pedida) podem aparecer "
    'como "sem uso" só porque o log correspondente já expirou — não '
    "necessariamente porque a tabela não foi acessada de verdade."
)

_SAVINGS_DISCLAIMER = (
    "Estimativa especulativa baseada no custo de scan REAL observado nos "
    "últimos 30 dias — não confirma que as queries filtram pela coluna de "
    "data candidata (o que de fato reduziria bytes escaneados via "
    "partition pruning). Se a query faz JOIN com outras tabelas grandes, o "
    "custo mostrado é o da query inteira, não isolado só desta tabela."
)


def _human_bytes(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000:
            return f"{value:.2f} {unit}"
        value /= 1000
    return f"{value:.2f} TB"


def _estimate_query_cost_usd(num_bytes: int) -> float:
    tib = num_bytes / (1024**4)
    return round(tib * settings.bigquery_price_usd_per_tib, 6)


def _estimate_storage_cost_usd(size_bytes: int, modified: datetime | None, now: datetime) -> float:
    is_long_term = (
        modified is not None and (now - modified).days >= _LONG_TERM_STORAGE_THRESHOLD_DAYS
    )
    price_per_gb = (
        settings.bigquery_storage_price_usd_per_gb_month_long_term
        if is_long_term
        else settings.bigquery_storage_price_usd_per_gb_month_active
    )
    gb = size_bytes / (1024**3)
    return round(gb * price_per_gb, 4)


def scan_unused_tables(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
    min_days_unused: MinDaysUnused = 30,
) -> UnusedTablesResponse:
    regions = discover_regions(project_id, client=client)
    all_tables = repository.list_all_table_refs(client, project_id, regions)
    events = repository.list_scan_events(logging_client, project_id, _UNUSED_TABLES_LOOKBACK_DAYS)

    last_access: dict[tuple[str, str], datetime] = {}
    for event in events:
        if event.timestamp is None:
            continue
        for ref in event.referenced_tables:
            if ref[0] != project_id:
                continue
            key = ref[1:]
            if key not in last_access or event.timestamp > last_access[key]:
                last_access[key] = event.timestamp

    table_refs = [f"{project_id}.{d}.{t}" for d, t in all_tables]
    metadata = get_tables_metadata(client, table_refs)

    now = datetime.now(UTC)
    unused: list[UnusedTable] = []
    for dataset_id, table_id in all_tables:
        last_at = last_access.get((dataset_id, table_id))
        days_since = (now - last_at).days if last_at else None
        if days_since is not None and days_since < min_days_unused:
            continue  # acessada dentro da janela pedida, não é "sem uso"

        bq_table = metadata.get(f"{project_id}.{dataset_id}.{table_id}")
        if bq_table is None:
            continue  # sumiu entre a listagem e o fetch (race)

        size_bytes = bq_table.num_bytes or 0
        unused.append(
            UnusedTable(
                dataset_id=dataset_id,
                table_id=table_id,
                size_bytes=size_bytes,
                size_human=_human_bytes(size_bytes),
                last_accessed_at=last_at,
                days_since_last_access=days_since,
                estimated_monthly_storage_cost_usd=_estimate_storage_cost_usd(
                    size_bytes, bq_table.modified, now
                ),
            )
        )

    unused.sort(key=lambda t: t.size_bytes, reverse=True)

    warning = None
    if not events:
        warning = _EMPTY_RESULT_WARNING.format(
            days=_UNUSED_TABLES_LOOKBACK_DAYS, project_id=project_id
        )
    elif min_days_unused > 30:
        warning = _RETENTION_CAVEAT.format(min_days_unused=min_days_unused)

    return UnusedTablesResponse(
        project_id=project_id,
        min_days_unused=min_days_unused,
        lookback_days=_UNUSED_TABLES_LOOKBACK_DAYS,
        tables=unused,
        warning=warning,
    )


def scan_partition_candidates(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
) -> PartitionCandidatesResponse:
    regions = discover_regions(project_id, client=client)
    all_tables = repository.list_all_table_refs(client, project_id, regions)
    table_refs = [f"{project_id}.{d}.{t}" for d, t in all_tables]
    metadata = get_tables_metadata(client, table_refs)

    size_candidates: list[tuple[str, str, bigquery.Table]] = []
    for dataset_id, table_id in all_tables:
        bq_table = metadata.get(f"{project_id}.{dataset_id}.{table_id}")
        if bq_table is None:
            continue
        if bq_table.time_partitioning is not None or bq_table.range_partitioning is not None:
            continue  # já particionada
        if (bq_table.num_bytes or 0) < _MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE:
            continue  # pequena demais pra valer a pena sinalizar
        size_candidates.append((dataset_id, table_id, bq_table))

    events = repository.list_scan_events(
        logging_client, project_id, _PARTITION_CANDIDATE_LOOKBACK_DAYS
    )
    billed_bytes_by_table: dict[tuple[str, str], int] = {}
    for event in events:
        if event.timestamp is None:
            continue
        for ref in event.referenced_tables:
            if ref[0] != project_id:
                continue
            key = ref[1:]
            billed_bytes_by_table[key] = (
                billed_bytes_by_table.get(key, 0) + event.total_billed_bytes
            )

    dataset_regions: dict[str, str] = {}
    candidates: list[PartitionCandidate] = []
    for dataset_id, table_id, bq_table in size_candidates:
        if dataset_id not in dataset_regions:
            dataset_regions[dataset_id] = resolve_dataset_region(
                client, project_id, dataset_id, regions
            )
        location = dataset_regions[dataset_id]

        date_columns = repository.get_date_like_columns(
            client, project_id, dataset_id, table_id, location
        )
        if not date_columns:
            continue  # sem coluna candidata, não é uma sugestão viável

        billed = billed_bytes_by_table.get((dataset_id, table_id), 0)
        observed_cost = _estimate_query_cost_usd(billed)
        conservative = round(observed_cost * _CONSERVATIVE_REDUCTION, 6) if billed > 0 else None
        optimistic = round(observed_cost * _OPTIMISTIC_REDUCTION, 6) if billed > 0 else None
        size_bytes = bq_table.num_bytes or 0

        candidates.append(
            PartitionCandidate(
                dataset_id=dataset_id,
                table_id=table_id,
                size_bytes=size_bytes,
                size_human=_human_bytes(size_bytes),
                row_count=bq_table.num_rows,
                candidate_partition_columns=date_columns,
                observed_billed_bytes_30d=billed,
                observed_cost_usd_30d=observed_cost,
                estimated_savings_usd_conservative=conservative,
                estimated_savings_usd_optimistic=optimistic,
                savings_disclaimer=_SAVINGS_DISCLAIMER if billed > 0 else None,
            )
        )

    candidates.sort(key=lambda c: c.observed_cost_usd_30d, reverse=True)

    return PartitionCandidatesResponse(
        project_id=project_id,
        lookback_days=_PARTITION_CANDIDATE_LOOKBACK_DAYS,
        candidates=candidates,
        warning=_EMPTY_RESULT_WARNING.format(
            days=_PARTITION_CANDIDATE_LOOKBACK_DAYS, project_id=project_id
        )
        if not events
        else None,
    )
