"""Orquestra o domínio quality: valida parâmetros, resolve região e colunas,
monta SQL via sql_builder, executa via repository, deriva as métricas
descritas na spec (tipo lógico, quality_flag, CV, duplicatas). api/v1 só
chama estas funções — CLAUDE.md proíbe lógica de negócio em api/.
"""

import re
import time
from datetime import UTC, datetime

from google.cloud import bigquery, firestore

from observability_hub.core.bigquery import discover_regions, resolve_dataset_region
from observability_hub.core.config import settings
from observability_hub.core.exceptions import (
    InvalidDateColumnError,
    InvalidSamplePercentError,
    ProfilingTimeoutError,
    TableNotFoundError,
)
from observability_hub.domains.quality import history_repository, repository, sql_builder
from observability_hub.domains.quality.schemas import (
    ColumnProfile,
    EstimateResponse,
    ExcludedColumn,
    Granularity,
    HistoryColumnSnapshot,
    InferredLogicalType,
    NullDistributionPoint,
    NullDistributionResponse,
    ProfilingHistoryResponse,
    ProfilingHistoryRun,
    ProfilingRequest,
    ProfilingRunResponse,
    QualityFlag,
    TableProfilingSummary,
    TopValue,
)

_PROFILING_TIMEOUT_SECONDS = 60.0
_TOP_N_MAX_DISTINCT = 50
_DATE_STRING_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Tipos físicos numéricos do BigQuery — têm prioridade sobre as heurísticas
# de distinct_count/distinct_pct (id, boolean, categorical): o tipo físico
# já responde a pergunta, não precisa inferir a partir da cardinalidade.
_NUMERIC_PHYSICAL_TYPES = {"INTEGER", "INT64", "FLOAT64", "NUMERIC", "BIGNUMERIC"}
_DATE_PHYSICAL_TYPES = {"DATE"}
_TIMESTAMP_PHYSICAL_TYPES = {"DATETIME", "TIMESTAMP"}


def _validate_sample_percent(sample_percent: float) -> None:
    if sample_percent < 1:
        raise InvalidSamplePercentError(sample_percent)


def _split_columns(raw_columns: list[dict]) -> tuple[list[dict], list[ExcludedColumn]]:
    profileable: list[dict] = []
    excluded: list[ExcludedColumn] = []
    for col in raw_columns:
        if sql_builder.is_excluded_type(col["data_type"]):
            excluded.append(
                ExcludedColumn(
                    column_name=col["column_name"],
                    reason=f"Tipo {col['data_type']} (STRUCT/ARRAY) não é suportado pelo profiling.",
                )
            )
        else:
            profileable.append(col)
    return profileable, excluded


def _available_date_columns(profileable: list[dict]) -> list[str]:
    return [
        c["column_name"]
        for c in profileable
        if c["data_type"].upper() in repository.DATE_COLUMN_TYPES
    ]


def _validate_date_column(date_column: str | None, profileable: list[dict]) -> None:
    if date_column is None:
        return
    available = _available_date_columns(profileable)
    if date_column not in available:
        raise InvalidDateColumnError(date_column, available)


def _resolve_location_and_columns(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str
) -> tuple[str, list[dict], list[ExcludedColumn], bool]:
    regions = discover_regions(project_id, client=client)
    location = resolve_dataset_region(client, project_id, dataset_id, regions)
    raw_columns = repository.get_table_columns(client, project_id, dataset_id, table_id, location)
    if not raw_columns:
        raise TableNotFoundError(project_id, dataset_id, table_id)
    profileable, excluded = _split_columns(raw_columns)
    is_view = repository.is_view(client, project_id, dataset_id, table_id, location)
    return location, profileable, excluded, is_view


def _remaining_budget(start: float, project_id: str, dataset_id: str, table_id: str) -> float:
    remaining = _PROFILING_TIMEOUT_SECONDS - (time.monotonic() - start)
    if remaining <= 0:
        raise ProfilingTimeoutError(project_id, dataset_id, table_id)
    return remaining


def _run_with_timeout_guard(project_id, dataset_id, table_id, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TimeoutError as exc:
        raise ProfilingTimeoutError(project_id, dataset_id, table_id) from exc


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


def _contains_at(value: object) -> bool:
    return isinstance(value, str) and "@" in value


def _matches_date_pattern(value: object) -> bool:
    return isinstance(value, str) and bool(_DATE_STRING_PATTERN.match(value))


def _is_numeric_string(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        float(value)
    except ValueError:
        return False
    return True


def _infer_logical_type(
    data_type: str,
    distinct_count: int,
    distinct_pct: float,
    min_value: object,
    max_value: object,
) -> InferredLogicalType:
    """Ordem de checagem por especificidade (não pela ordem da tabela da
    spec, que é auto-contraditória de forma literal: distinct_count<50
    sempre é verdade quando distinct_count==2, então "boolean" nunca seria
    alcançável se "categorical" fosse checado primeiro).

    Tipo físico (DATE/DATETIME/TIMESTAMP/numérico) é checado antes de
    qualquer heurística de cardinalidade — o dado já diz o que é, não
    precisa inferir de distinct_count/distinct_pct."""
    data_type_upper = data_type.upper()
    is_string = data_type_upper == "STRING"

    if data_type_upper in _DATE_PHYSICAL_TYPES:
        return InferredLogicalType.DATE
    if data_type_upper in _TIMESTAMP_PHYSICAL_TYPES:
        return InferredLogicalType.TIMESTAMP
    if data_type_upper in _NUMERIC_PHYSICAL_TYPES:
        return InferredLogicalType.NUMERIC
    if distinct_pct > 90:
        return InferredLogicalType.ID
    if distinct_count == 2:
        return InferredLogicalType.BOOLEAN
    if is_string:
        if _contains_at(min_value) or _contains_at(max_value):
            return InferredLogicalType.EMAIL
        if _matches_date_pattern(min_value) and _matches_date_pattern(max_value):
            return InferredLogicalType.DATE_STRING
        if _is_numeric_string(min_value) and _is_numeric_string(max_value):
            return InferredLogicalType.NUMERIC_STRING
    if distinct_count < _TOP_N_MAX_DISTINCT:
        return InferredLogicalType.CATEGORICAL
    if is_string and distinct_pct > 50:
        return InferredLogicalType.FREE_TEXT
    return InferredLogicalType.UNKNOWN


def _coefficient_of_variation(
    data_type: str, avg_value: object, stddev_value: object
) -> float | None:
    if not sql_builder.is_numeric_type(data_type):
        return None
    if not isinstance(avg_value, int | float) or avg_value == 0:
        return None
    if not isinstance(stddev_value, int | float):
        return None
    return round(stddev_value / avg_value * 100, 4)


def _quality_flag(completeness_pct: float) -> QualityFlag:
    if completeness_pct >= 80:
        return QualityFlag.OK
    if completeness_pct >= 50:
        return QualityFlag.WARNING
    return QualityFlag.CRITICAL


def estimate_profiling(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: ProfilingRequest,
) -> EstimateResponse:
    _validate_sample_percent(request.sample_percent)
    _location, profileable, _excluded, is_view = _resolve_location_and_columns(
        client, project_id, dataset_id, table_id
    )
    _validate_date_column(request.date_column, profileable)

    columns = [sql_builder.ProfileableColumn(c["column_name"], c["data_type"]) for c in profileable]
    sql = sql_builder.build_main_query(
        project_id,
        dataset_id,
        table_id,
        columns,
        request.sample_percent,
        request.uniqueness_method,
        request.date_column,
        request.date_window_days,
        is_view=is_view,
    )
    estimated_bytes = repository.dry_run(client, project_id, sql)
    return EstimateResponse(
        estimated_bytes=estimated_bytes,
        estimated_bytes_human=_human_bytes(estimated_bytes),
        estimated_cost_usd=_estimate_cost_usd(estimated_bytes),
        sql=sql,
    )


def run_profiling(
    client: bigquery.Client,
    firestore_client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: ProfilingRequest,
    executed_by: str,
) -> ProfilingRunResponse:
    start = time.monotonic()
    _validate_sample_percent(request.sample_percent)
    location, profileable, excluded, is_view = _resolve_location_and_columns(
        client, project_id, dataset_id, table_id
    )
    _validate_date_column(request.date_column, profileable)

    columns = [sql_builder.ProfileableColumn(c["column_name"], c["data_type"]) for c in profileable]
    sql = sql_builder.build_main_query(
        project_id,
        dataset_id,
        table_id,
        columns,
        request.sample_percent,
        request.uniqueness_method,
        request.date_column,
        request.date_window_days,
        is_view=is_view,
    )
    budget = _remaining_budget(start, project_id, dataset_id, table_id)
    main_result = _run_with_timeout_guard(
        project_id,
        dataset_id,
        table_id,
        repository.execute_main_query,
        client,
        project_id,
        sql,
        budget,
    )

    total_table_rows = (
        repository.get_total_table_rows(client, project_id, dataset_id, table_id, location) or 0
    )
    total_sampled_rows: int = main_result["_total_sampled_rows"]
    approx_distinct_rows: int = main_result["_approx_distinct_rows"]
    duplicate_rows = max(total_sampled_rows - approx_distinct_rows, 0)
    duplicate_pct = (duplicate_rows / total_sampled_rows * 100) if total_sampled_rows else 0.0

    column_profiles: list[ColumnProfile] = []
    for col in profileable:
        aliases = sql_builder.column_field_aliases(
            col["column_name"], col["data_type"], request.uniqueness_method
        )
        count_filled: int = main_result[aliases["count_filled"]]
        distinct_count: int = main_result[aliases["distinct"]]
        min_value = main_result[aliases["min"]]
        max_value = main_result[aliases["max"]]
        avg_value = main_result.get(aliases.get("avg", ""))
        stddev_value = main_result.get(aliases.get("stddev", ""))

        null_count = total_sampled_rows - count_filled
        completeness_pct = (count_filled / total_sampled_rows * 100) if total_sampled_rows else 0.0
        distinct_pct = (distinct_count / total_sampled_rows * 100) if total_sampled_rows else 0.0

        top_values: list[TopValue] | None = None
        if total_sampled_rows > 0 and distinct_count < _TOP_N_MAX_DISTINCT:
            budget = _remaining_budget(start, project_id, dataset_id, table_id)
            top_n_sql = sql_builder.build_top_n_query(
                project_id,
                dataset_id,
                table_id,
                col["column_name"],
                request.sample_percent,
                request.date_column,
                request.date_window_days,
                is_view=is_view,
            )
            raw_top = _run_with_timeout_guard(
                project_id,
                dataset_id,
                table_id,
                repository.execute_top_n_query,
                client,
                project_id,
                top_n_sql,
                budget,
            )
            top_values = [
                TopValue(
                    value=r["value"],
                    count=r["count"],
                    pct=round((r["count"] / total_sampled_rows * 100), 2)
                    if total_sampled_rows
                    else 0.0,
                )
                for r in raw_top
            ]

        column_profiles.append(
            ColumnProfile(
                column_name=col["column_name"],
                data_type=col["data_type"],
                is_nullable=col["is_nullable"],
                completeness_pct=round(completeness_pct, 2),
                null_count=null_count,
                distinct_count=distinct_count,
                distinct_pct=round(distinct_pct, 4),
                min_value=min_value,
                max_value=max_value,
                top_values=top_values,
                inferred_logical_type=_infer_logical_type(
                    col["data_type"], distinct_count, distinct_pct, min_value, max_value
                ),
                coefficient_of_variation=_coefficient_of_variation(
                    col["data_type"], avg_value, stddev_value
                ),
                quality_flag=_quality_flag(completeness_pct),
            )
        )

    overall_density = (
        sum(c.completeness_pct for c in column_profiles) / len(column_profiles)
        if column_profiles
        else 0.0
    )
    rounded_density = round(overall_density, 2)
    rounded_duplicate_pct = round(duplicate_pct, 2)

    # Salva pro histórico de qualidade (domains/quality/history_repository.py)
    # poder mostrar a evolução da tabela ao longo do tempo sem precisar
    # reprofilar — subcoleção compartilhada, um doc novo por run.
    history_repository.save_run(
        firestore_client,
        project_id,
        dataset_id,
        table_id,
        overall_density=rounded_density,
        estimated_duplicate_pct=rounded_duplicate_pct,
        executed_by=executed_by,
        columns=[
            {
                "column_name": c.column_name,
                "completeness_pct": c.completeness_pct,
                "quality_flag": c.quality_flag.value,
            }
            for c in column_profiles
        ],
    )

    return ProfilingRunResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        executed_at=datetime.now(UTC),
        parameters=request,
        sql=sql,
        table_summary=TableProfilingSummary(
            total_sampled_rows=total_sampled_rows,
            total_table_rows=total_table_rows,
            estimated_duplicate_rows=duplicate_rows,
            estimated_duplicate_pct=rounded_duplicate_pct,
            overall_density=rounded_density,
        ),
        columns=column_profiles,
        excluded_columns=excluded,
    )


def get_null_distribution(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    column_name: str,
    date_column: str,
    date_window_days: int,
    granularity: Granularity,
) -> NullDistributionResponse:
    _location, profileable, _excluded, _is_view = _resolve_location_and_columns(
        client, project_id, dataset_id, table_id
    )
    _validate_date_column(date_column, profileable)
    date_column_type = next(c["data_type"] for c in profileable if c["column_name"] == date_column)

    sql = sql_builder.build_null_distribution_query(
        project_id,
        dataset_id,
        table_id,
        column_name,
        date_column,
        date_column_type,
        date_window_days,
        granularity,
    )
    raw_series = _run_with_timeout_guard(
        project_id,
        dataset_id,
        table_id,
        repository.execute_null_distribution_query,
        client,
        project_id,
        sql,
        _PROFILING_TIMEOUT_SECONDS,
    )
    series = [
        NullDistributionPoint(
            period=str(point["period"]),
            null_count=point["null_count"],
            null_pct=round((point["null_count"] / point["total_rows"] * 100), 2)
            if point["total_rows"]
            else 0.0,
            total_rows=point["total_rows"],
        )
        for point in raw_series
    ]
    return NullDistributionResponse(
        column_name=column_name,
        date_column=date_column,
        granularity=granularity,
        series=series,
    )


def get_quality_history(
    firestore_client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> ProfilingHistoryResponse:
    """Só Firestore — não toca BigQuery, o histórico independe do estado
    atual da tabela (inclusive se ela já tiver sido apagada)."""
    raw_runs = history_repository.list_runs(firestore_client, project_id, dataset_id, table_id)
    runs = [
        ProfilingHistoryRun(
            executed_at=raw["executed_at"],
            executed_by=raw["executed_by"],
            overall_density=raw["overall_density"],
            estimated_duplicate_pct=raw["estimated_duplicate_pct"],
            columns=[HistoryColumnSnapshot(**c) for c in raw["columns"]],
        )
        for raw in raw_runs
    ]
    return ProfilingHistoryResponse(
        project_id=project_id, dataset_id=dataset_id, table_id=table_id, runs=runs
    )
