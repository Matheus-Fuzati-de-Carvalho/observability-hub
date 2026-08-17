"""Orquestra o domínio pii: resolve colunas elegíveis, monta SQL via
sql_builder, executa via repository e deriva flagging/confidence por
coluna. api/v1 só chama estas funções — CLAUDE.md proíbe lógica de
negócio em api/.

Garantia de privacidade estrutural: o matching roda inteiramente em SQL
(REGEXP_CONTAINS + COUNTIF dentro do BigQuery) — nenhuma função aqui
jamais vê um valor de coluna real, só contagens agregadas. Ver
docs/specs/pii.md.
"""

import threading
import time
from datetime import UTC, datetime

from google.cloud import bigquery, firestore

from observability_hub.core.bigquery import discover_regions, resolve_dataset_region
from observability_hub.core.config import settings
from observability_hub.core.exceptions import (
    InvalidSamplePercentError,
    PiiScanTimeoutError,
    TableNotFoundError,
)
from observability_hub.domains.pii import history_repository, repository, sql_builder
from observability_hub.domains.pii.schemas import (
    PiiColumnResult,
    PiiEstimateResponse,
    PiiExcludedColumn,
    PiiScanRequest,
    PiiScanResponse,
    PiiType,
    PiiTypeMatch,
)

_PII_SCAN_TIMEOUT_SECONDS = 60.0
_SCAN_CACHE_TTL_SECONDS = 300

# Mesmo padrão de domains/catalog/repository.py::_partition_stats_cache —
# dict em memória por processo, protegido por lock, TTL curto pra não
# recobrar a mesma query dentro de uma janela de poucos minutos.
_scan_cache: dict[str, tuple[float, PiiScanResponse]] = {}
_scan_cache_lock = threading.Lock()


def _validate_sample_percent(sample_percent: float) -> None:
    if sample_percent < 1:
        raise InvalidSamplePercentError(sample_percent)


def _is_excluded_type(data_type: str) -> bool:
    return data_type.upper() != "STRING"


def _split_columns(raw_columns: list[dict]) -> tuple[list[dict], list[PiiExcludedColumn]]:
    candidates: list[dict] = []
    excluded: list[PiiExcludedColumn] = []
    for col in raw_columns:
        if _is_excluded_type(col["data_type"]):
            excluded.append(
                PiiExcludedColumn(
                    column_name=col["column_name"],
                    reason=f"Tipo {col['data_type']} não é STRING — sem padrão de PII "
                    "aplicável nesta versão.",
                )
            )
        else:
            candidates.append(col)
    return candidates, excluded


def _resolve_location_and_columns(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str
) -> tuple[str, list[dict], list[PiiExcludedColumn], bool]:
    regions = discover_regions(project_id, client=client)
    location = resolve_dataset_region(client, project_id, dataset_id, regions)
    raw_columns = repository.get_table_columns(client, project_id, dataset_id, table_id, location)
    if not raw_columns:
        raise TableNotFoundError(project_id, dataset_id, table_id)
    candidates, excluded = _split_columns(raw_columns)
    is_view = repository.is_view(client, project_id, dataset_id, table_id, location)
    return location, candidates, excluded, is_view


def _human_bytes(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000:
            return f"{value:.2f} {unit}"
        value /= 1000
    return f"{value:.2f} TB"


def _estimate_cost_usd(num_bytes: int) -> float:
    tib = num_bytes / (1024**4)
    return round(tib * settings.bigquery_price_usd_per_tib, 8)


def _cache_key(
    project_id: str,
    dataset_id: str,
    table_id: str,
    sample_percent: float,
    match_threshold_pct: float,
) -> str:
    return f"{project_id}.{dataset_id}.{table_id}:{sample_percent}:{match_threshold_pct}"


def _cache_get(key: str) -> PiiScanResponse | None:
    now = time.monotonic()
    with _scan_cache_lock:
        cached = _scan_cache.get(key)
    if cached is not None and now - cached[0] < _SCAN_CACHE_TTL_SECONDS:
        return cached[1]
    return None


def _cache_set(key: str, response: PiiScanResponse) -> None:
    with _scan_cache_lock:
        _scan_cache[key] = (time.monotonic(), response)


def _column_result(
    column_name: str,
    data_type: str,
    sample_non_null_count: int | None,
    type_matches: list[PiiTypeMatch],
) -> PiiColumnResult:
    name_matches = [PiiType(t) for t in sql_builder.name_match_types(column_name)]
    sample_flagged = any(m.flagged for m in type_matches)
    flagged = bool(name_matches) or sample_flagged
    confidence: str | None = None
    if name_matches and sample_flagged:
        confidence = "high"
    elif name_matches or sample_flagged:
        confidence = "medium"
    return PiiColumnResult(
        column_name=column_name,
        data_type=data_type,
        name_match_types=name_matches,
        sample_non_null_count=sample_non_null_count,
        sample_matches=type_matches,
        flagged=flagged,
        confidence=confidence,
    )


def estimate_pii_scan(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: PiiScanRequest,
) -> PiiEstimateResponse:
    _validate_sample_percent(request.sample_percent)
    _location, candidates, _excluded, is_view = _resolve_location_and_columns(
        client, project_id, dataset_id, table_id
    )

    # is_view: run_pii_scan pula a query paga inteiramente pra view (ver
    # docs/specs/pii.md, "Casos de borda") — a estimativa reflete isso,
    # não tem sentido estimar custo de uma query que nunca vai rodar.
    column_names = [] if is_view else [c["column_name"] for c in candidates]
    sql = sql_builder.build_scan_query(
        project_id, dataset_id, table_id, column_names, request.sample_percent, is_view
    )
    if sql is None:
        return PiiEstimateResponse(
            estimated_bytes=0, estimated_bytes_human="0.00 B", estimated_cost_usd=0.0, sql=None
        )

    estimated_bytes = repository.dry_run(client, project_id, sql)
    return PiiEstimateResponse(
        estimated_bytes=estimated_bytes,
        estimated_bytes_human=_human_bytes(estimated_bytes),
        estimated_cost_usd=_estimate_cost_usd(estimated_bytes),
        sql=sql,
    )


def run_pii_scan(
    client: bigquery.Client,
    firestore_client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: PiiScanRequest,
    executed_by: str,
) -> PiiScanResponse:
    _validate_sample_percent(request.sample_percent)
    cache_key = _cache_key(
        project_id, dataset_id, table_id, request.sample_percent, request.match_threshold_pct
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    start = time.monotonic()
    _location, candidates, excluded, is_view = _resolve_location_and_columns(
        client, project_id, dataset_id, table_id
    )

    # is_view: query paga é pulada inteiramente (VIEW/MATERIALIZED VIEW não
    # suportam TABLESAMPLE, e rodar sem amostragem escanearia a view
    # inteira sem aviso prévio de custo) — só a heurística de nome roda.
    column_names = [] if is_view else [c["column_name"] for c in candidates]
    sql = sql_builder.build_scan_query(
        project_id, dataset_id, table_id, column_names, request.sample_percent, is_view
    )

    warning: str | None = None
    if is_view:
        warning = (
            "Tabela é VIEW/MATERIALIZED VIEW — TABLESAMPLE não é suportado, só a "
            "heurística de nome foi avaliada."
        )
        columns = [_column_result(c["column_name"], c["data_type"], None, []) for c in candidates]
    elif sql is None:
        warning = "Nenhuma coluna STRING encontrada — só a heurística de nome foi avaliada."
        columns = [_column_result(c["column_name"], c["data_type"], None, []) for c in candidates]
    else:
        remaining = _PII_SCAN_TIMEOUT_SECONDS - (time.monotonic() - start)
        if remaining <= 0:
            raise PiiScanTimeoutError(project_id, dataset_id, table_id)
        try:
            result_row = repository.execute_scan_query(client, project_id, sql, remaining)
        except TimeoutError as exc:
            raise PiiScanTimeoutError(project_id, dataset_id, table_id) from exc

        columns = []
        for col in candidates:
            name = col["column_name"]
            non_null_count: int = result_row[f"{name}__non_null"]
            type_matches: list[PiiTypeMatch] = []
            for pii_type in sql_builder.PII_PATTERNS:
                match_count: int = result_row[f"{name}__{pii_type}"]
                if match_count <= 0:
                    continue
                match_ratio = match_count / non_null_count if non_null_count else 0.0
                type_matches.append(
                    PiiTypeMatch(
                        pii_type=PiiType(pii_type),
                        match_count=match_count,
                        match_ratio=round(match_ratio, 4),
                        flagged=match_ratio * 100 >= request.match_threshold_pct,
                    )
                )
            columns.append(_column_result(name, col["data_type"], non_null_count, type_matches))

    response = PiiScanResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        executed_at=datetime.now(UTC),
        is_view=is_view,
        parameters=request,
        sql=sql,
        columns=columns,
        excluded_columns=excluded,
        warning=warning,
    )
    _cache_set(cache_key, response)

    # Só grava histórico em cache miss (chegou até aqui) — um cache hit
    # (linha 194) devolve o resultado antigo sem rodar nada de novo, então
    # não representa uma execução real.
    history_repository.save_scan(
        firestore_client,
        project_id,
        dataset_id,
        table_id,
        executed_by=executed_by,
        flagged_columns_count=sum(1 for c in columns if c.flagged),
        columns=[
            {"column_name": c.column_name, "flagged": c.flagged, "confidence": c.confidence}
            for c in columns
        ],
    )

    return response
