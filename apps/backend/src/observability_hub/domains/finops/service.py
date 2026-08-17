"""Orquestra o domínio finops: scanner de desperdício (tabelas sem uso,
candidatas a particionamento) e budget (custo agrupável por
tabela/usuário/dia/mês/ano, queries mais caras, projeção do mês) —
combina enumeração de tabelas (BigQuery INFORMATION_SCHEMA +
client.get_table() via core/bigquery.py) com audit logs de jobs (Cloud
Logging, via repository). api/v1 só chama estas funções — CLAUDE.md
proíbe lógica de negócio em api/.
"""

import calendar
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from observability_hub.core.bigquery import (
    discover_regions,
    get_tables_metadata,
    resolve_dataset_region,
)
from observability_hub.core.config import settings
from observability_hub.core.exceptions import InvalidSamplePercentError
from observability_hub.domains.finops import repository, sql_builder
from observability_hub.domains.finops.repository import ScanEvent, TableRefTuple
from observability_hub.domains.finops.schemas import (
    BudgetGroupBy,
    BudgetResponse,
    ColumnTypeCandidate,
    ColumnTypeEstimateResponse,
    ColumnTypeScanRequest,
    ColumnTypeSuggestion,
    ColumnTypeSuggestionsResponse,
    CostGroup,
    CostlyQuery,
    CostProjection,
    MinDaysUnused,
    PartitionCandidate,
    PartitionCandidatesResponse,
    SuggestedColumnType,
    UnusedTable,
    UnusedTablesResponse,
)

_UNUSED_TABLES_LOOKBACK_DAYS = 90
_PARTITION_CANDIDATE_LOOKBACK_DAYS = 30
_LONG_TERM_STORAGE_THRESHOLD_DAYS = 90
_MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE = 1_073_741_824  # 1 GB
_CONSERVATIVE_REDUCTION = 0.30
_OPTIMISTIC_REDUCTION = 0.70
_BUDGET_TOP_N_DEFAULT = 10
_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS = 120.0
_COLUMN_TYPE_SCAN_MAX_WORKERS = 4
_STORAGE_BYTES_OVERHEAD = (
    2  # overhead fixo de STRING no storage do BQ, ver docs/specs/finops-column-types.md
)

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

_BUDGET_RETENTION_CAVEAT = (
    "Já estamos {days} dias dentro do mês, e Data Access audit logs no "
    "Cloud Logging têm retenção padrão de 30 dias (salvo bucket/sink "
    "customizado). Se esse for o caso aqui, o início do mês pode estar "
    "faltando neste relatório — custo agrupado, top queries e projeção "
    "ficariam subestimados."
)

_COLUMN_TYPE_PARTIAL_RESULT_WARNING = (
    "Orçamento de tempo do scan ({budget}s) esgotou antes de escanear todas "
    "as tabelas elegíveis — resultado parcial, baseado em {scanned} de "
    "{total} tabelas."
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


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


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


def _group_keys(
    group_by: BudgetGroupBy, event: ScanEvent, real_tables: list[TableRefTuple]
) -> list[str]:
    """Uma chave por tabela real tocada (fan-out, mesma lógica de
    by_dataset da v1 — uma query com JOIN entre tabelas conta em cada
    uma) pra group_by=TABLE; uma chave só pras demais dimensões, que são
    por evento, não por tabela."""
    if group_by == BudgetGroupBy.TABLE:
        return sorted({f"{p}.{d}.{t}" for p, d, t in real_tables})
    if group_by == BudgetGroupBy.USER:
        return [event.principal_email]
    assert event.timestamp is not None  # já filtrado antes de chamar
    if group_by == BudgetGroupBy.DAY:
        return [event.timestamp.date().isoformat()]
    if group_by == BudgetGroupBy.MONTH:
        return [event.timestamp.strftime("%Y-%m")]
    return [str(event.timestamp.year)]  # YEAR


def get_budget(
    logging_client: cloud_logging.Client,
    project_id: str,
    group_by: BudgetGroupBy = BudgetGroupBy.TABLE,
    limit: int = _BUDGET_TOP_N_DEFAULT,
) -> BudgetResponse:
    now = datetime.now(UTC)
    month_start = _month_start(now)
    lookback_days = (now - month_start).days + 1

    events = repository.list_scan_events(logging_client, project_id, lookback_days)

    group_bytes: dict[str, int] = {}
    group_jobs: dict[str, int] = {}
    queries: list[CostlyQuery] = []
    total_billed_bytes = 0

    for event in events:
        if event.timestamp is None or event.timestamp < month_start:
            continue
        if event.total_billed_bytes <= 0:
            continue

        real_tables = [ref for ref in event.referenced_tables if ref[0] == project_id]
        if not real_tables:
            # Só referencia INFORMATION_SCHEMA (já filtrado em
            # repository._parse_table_ref) ou tabela de outro projeto —
            # não é atividade de dado real deste projeto, não entra em
            # nenhuma agregação de budget (ver docs/specs/finops-budget.md,
            # "Casos de borda").
            continue

        total_billed_bytes += event.total_billed_bytes

        for key in _group_keys(group_by, event, real_tables):
            group_bytes[key] = group_bytes.get(key, 0) + event.total_billed_bytes
            group_jobs[key] = group_jobs.get(key, 0) + 1

        queries.append(
            CostlyQuery(
                job_id=event.job_id,
                principal_email=event.principal_email,
                executed_at=event.timestamp,
                billed_bytes=event.total_billed_bytes,
                cost_usd=_estimate_query_cost_usd(event.total_billed_bytes),
                tables=[f"{p}.{d}.{t}" for p, d, t in real_tables],
                query_text=event.query_text,
            )
        )

    groups = sorted(
        (
            CostGroup(
                key=key,
                cost_usd=_estimate_query_cost_usd(billed),
                billed_bytes=billed,
                job_count=group_jobs[key],
            )
            for key, billed in group_bytes.items()
        ),
        key=lambda g: g.cost_usd,
        reverse=True,
    )

    top_queries = sorted(queries, key=lambda q: q.cost_usd, reverse=True)[:limit]

    total_cost_usd = _estimate_query_cost_usd(total_billed_bytes)
    daily_average = total_cost_usd / lookback_days if lookback_days else 0.0
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    projection = CostProjection(
        days_elapsed=lookback_days,
        days_in_month=days_in_month,
        cost_so_far_usd=total_cost_usd,
        daily_average_usd=round(daily_average, 6),
        projected_month_total_usd=round(daily_average * days_in_month, 6),
    )

    warning = None
    if not events:
        warning = _EMPTY_RESULT_WARNING.format(days=lookback_days, project_id=project_id)
    elif lookback_days > 30:
        warning = _BUDGET_RETENTION_CAVEAT.format(days=lookback_days)

    return BudgetResponse(
        project_id=project_id,
        period_start=month_start,
        lookback_days=lookback_days,
        group_by=group_by,
        groups=groups,
        total_cost_usd=total_cost_usd,
        top_queries=top_queries,
        projection=projection,
        warning=warning,
    )


# Tabela elegível pra sugestão de tipo de coluna: (dataset_id, table_id,
# location, string_columns, bq_table). string_columns nunca vazio aqui —
# tabelas sem coluna STRING já são descartadas em _resolve_eligible_tables.
_EligibleTable = tuple[str, str, str, list[str], bigquery.Table]


def _validate_sample_percent(sample_percent: float) -> None:
    if sample_percent < 1:
        raise InvalidSamplePercentError(sample_percent)


def _parse_scoped_tables(tables: list[str]) -> list[tuple[str, str]]:
    """ "dataset_id.table_id" -> (dataset_id, table_id). partition() no
    primeiro ponto — nome de dataset/tabela do BigQuery não aceita ponto
    (só letra, número, underscore), então é seguro."""
    parsed: list[tuple[str, str]] = []
    for entry in tables:
        dataset_id, _sep, table_id = entry.partition(".")
        if dataset_id and table_id:
            parsed.append((dataset_id, table_id))
    return parsed


def _resolve_eligible_tables(
    client: bigquery.Client, project_id: str, scope: list[str] | None = None
) -> tuple[list[_EligibleTable], int]:
    """Descobre, em paralelo por tabela (INFORMATION_SCHEMA, custo $0 —
    mesmo racional de repository.list_all_table_refs), quais tabelas têm
    pelo menos uma coluna STRING e não são VIEW/MATERIALIZED VIEW.
    Retorna (elegíveis, tables_skipped_view) — usado tanto por estimate
    quanto por run, pra garantir que os dois concordam em quais tabelas
    entram na conta.

    scope=None (ou lista vazia) enumera TODAS as tabelas do projeto via
    repository.list_all_table_refs — inviável em produção (ver
    docs/specs/finops-column-types.md, "Escopo de execução"), mas
    suportado pra flexibilidade da API/testes. Com scope, pula
    list_all_table_refs inteiramente (não enumera o projeto todo só pra
    filtrar depois) e resolve region/is_view/colunas só pras tabelas
    pedidas."""
    regions = discover_regions(project_id, client=client)
    if scope:
        all_tables = _parse_scoped_tables(scope)
    else:
        all_tables = repository.list_all_table_refs(client, project_id, regions)
    table_refs = [f"{project_id}.{d}.{t}" for d, t in all_tables]
    metadata = get_tables_metadata(client, table_refs)

    dataset_regions: dict[str, str] = {}
    for dataset_id, _table_id in all_tables:
        if dataset_id not in dataset_regions:
            dataset_regions[dataset_id] = resolve_dataset_region(
                client, project_id, dataset_id, regions
            )

    def _resolve_one(item: tuple[str, str]) -> tuple[str, _EligibleTable | None, bool]:
        dataset_id, table_id = item
        bq_table = metadata.get(f"{project_id}.{dataset_id}.{table_id}")
        if bq_table is None:
            return "skip", None, False
        location = dataset_regions[dataset_id]
        if repository.is_view(client, project_id, dataset_id, table_id, location):
            return "view", None, True
        string_columns = repository.get_string_columns(
            client, project_id, dataset_id, table_id, location
        )
        if not string_columns:
            return "skip", None, False
        return "eligible", (dataset_id, table_id, location, string_columns, bq_table), False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_resolve_one, all_tables))

    eligible: list[_EligibleTable] = []
    tables_skipped_view = 0
    for status, table, is_view_row in results:
        if status == "eligible" and table is not None:
            eligible.append(table)
        elif is_view_row:
            tables_skipped_view += 1

    return eligible, tables_skipped_view


def _pick_suggestion(
    column_name: str, result_row: dict, row_count: int | None
) -> ColumnTypeSuggestion | None:
    """Primeiro tipo candidato (em sql_builder.CANDIDATE_TYPES, do mais
    estreito pro mais largo) com 100% de match no não-nulo amostrado
    vence — nunca "a maioria bate". Só vira sugestão se além disso
    houver economia de bytes real (avg_current_bytes > bytes fixos do
    tipo sugerido) — ver docs/specs/finops-column-types.md, "Critério de
    sugestão"."""
    non_null_count: int = result_row[f"{column_name}__non_null"]
    if non_null_count <= 0:
        return None

    avg_current_bytes = _STORAGE_BYTES_OVERHEAD + (result_row[f"{column_name}__avg_bytes"] or 0.0)

    matched_type: str | None = None
    for candidate_type in sql_builder.CANDIDATE_TYPES:
        if result_row[f"{column_name}__{candidate_type}"] == non_null_count:
            matched_type = candidate_type
            break
    if matched_type is None:
        return None

    suggested_bytes = sql_builder.TYPE_FIXED_BYTES[matched_type]
    if avg_current_bytes <= suggested_bytes:
        return None  # trocar não economizaria — ver "Casos de borda"

    savings_gb = (avg_current_bytes - suggested_bytes) * (row_count or 0) / (1024**3)
    savings_usd = round(savings_gb * settings.bigquery_storage_price_usd_per_gb_month_active, 6)

    return ColumnTypeSuggestion(
        column_name=column_name,
        current_type="STRING",
        suggested_type=SuggestedColumnType(matched_type),
        sample_non_null_count=non_null_count,
        avg_current_bytes=round(avg_current_bytes, 2),
        suggested_type_bytes=suggested_bytes,
        estimated_storage_savings_usd_month=savings_usd,
    )


def estimate_column_type_suggestions(
    client: bigquery.Client,
    project_id: str,
    request: ColumnTypeScanRequest,
) -> ColumnTypeEstimateResponse:
    """Dry-run gratuito (nenhuma query paga) — soma os bytes que seriam
    processados por cada query de scan elegível."""
    _validate_sample_percent(request.sample_percent)
    eligible, tables_skipped_view = _resolve_eligible_tables(client, project_id, request.tables)

    total_bytes = 0
    columns_scanned = 0
    for dataset_id, table_id, _location, string_columns, _bq_table in eligible:
        sql = sql_builder.build_scan_query(
            project_id, dataset_id, table_id, string_columns, request.sample_percent, False
        )
        assert sql is not None  # string_columns nunca vazio em _EligibleTable
        total_bytes += repository.dry_run(client, project_id, sql)
        columns_scanned += len(string_columns)

    return ColumnTypeEstimateResponse(
        project_id=project_id,
        tables_scanned=len(eligible),
        tables_skipped_view=tables_skipped_view,
        columns_scanned=columns_scanned,
        estimated_bytes=total_bytes,
        estimated_bytes_human=_human_bytes(total_bytes),
        estimated_cost_usd=_estimate_query_cost_usd(total_bytes),
    )


def run_column_type_suggestions(
    client: bigquery.Client,
    project_id: str,
    request: ColumnTypeScanRequest,
) -> ColumnTypeSuggestionsResponse:
    """Executa de fato — uma query TABLESAMPLE por tabela elegível, em
    paralelo, com orçamento total de _COLUMN_TYPE_SCAN_TIMEOUT_SECONDS
    pro lote inteiro. Se o tempo acabar no meio, retorna as tabelas já
    escaneadas com warning de resultado parcial em vez de lançar erro —
    parcial ainda tem valor aqui (lista de oportunidades), diferente de
    um scan de tabela única em pii/quality."""
    _validate_sample_percent(request.sample_percent)
    started = time.monotonic()
    eligible, tables_skipped_view = _resolve_eligible_tables(client, project_id, request.tables)

    def _scan_one(item: _EligibleTable) -> ColumnTypeCandidate | None:
        dataset_id, table_id, _location, string_columns, bq_table = item
        sql = sql_builder.build_scan_query(
            project_id, dataset_id, table_id, string_columns, request.sample_percent, False
        )
        assert sql is not None
        remaining = _COLUMN_TYPE_SCAN_TIMEOUT_SECONDS - (time.monotonic() - started)
        result_row = repository.execute_scan_query(client, project_id, sql, max(remaining, 1.0))
        suggestions = [
            suggestion
            for column_name in string_columns
            if (suggestion := _pick_suggestion(column_name, result_row, bq_table.num_rows))
            is not None
        ]
        if not suggestions:
            return None
        return ColumnTypeCandidate(
            dataset_id=dataset_id,
            table_id=table_id,
            size_bytes=bq_table.num_bytes or 0,
            row_count=bq_table.num_rows,
            suggestions=suggestions,
        )

    candidates: list[ColumnTypeCandidate] = []
    tables_scanned = 0
    partial = False

    if eligible:
        # shutdown(wait=False, cancel_futures=True) em vez do `with` padrão
        # (que bloqueia em shutdown(wait=True) até TODAS as futures
        # terminarem, mesmo as ainda não iniciadas) — sem isso o timeout do
        # as_completed() não encurta o tempo total de verdade. client é
        # module-level (@lru_cache em core/bigquery.py), sobrevive à
        # resposta, então deixar futures em voo terminando em background é
        # seguro.
        pool = ThreadPoolExecutor(max_workers=_COLUMN_TYPE_SCAN_MAX_WORKERS)
        futures = {pool.submit(_scan_one, item): item for item in eligible}
        try:
            budget = max(_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS - (time.monotonic() - started), 0.0)
            for future in as_completed(futures, timeout=budget):
                result = future.result()
                tables_scanned += 1
                if result is not None:
                    candidates.append(result)
        except TimeoutError:
            partial = True
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    candidates.sort(
        key=lambda c: sum(s.estimated_storage_savings_usd_month for s in c.suggestions),
        reverse=True,
    )

    warning = None
    if partial:
        warning = _COLUMN_TYPE_PARTIAL_RESULT_WARNING.format(
            budget=int(_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS),
            scanned=tables_scanned,
            total=len(eligible),
        )

    return ColumnTypeSuggestionsResponse(
        project_id=project_id,
        executed_at=datetime.now(UTC),
        sample_percent=request.sample_percent,
        tables_scanned=tables_scanned,
        tables_skipped_view=tables_skipped_view,
        candidates=candidates,
        warning=warning,
    )
