from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class UniquenessMethod(str, Enum):
    APPROX = "approx"
    EXACT = "exact"


class InferredLogicalType(str, Enum):
    ID = "id"
    CATEGORICAL = "categorical"
    EMAIL = "email"
    DATE_STRING = "date_string"
    NUMERIC_STRING = "numeric_string"
    BOOLEAN = "boolean"
    FREE_TEXT = "free_text"
    NUMERIC = "numeric"
    DATE = "date"
    TIMESTAMP = "timestamp"
    UNKNOWN = "unknown"


class QualityFlag(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


class Granularity(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class ProfilingRequest(BaseModel):
    sample_percent: float = 100
    uniqueness_method: UniquenessMethod = UniquenessMethod.APPROX
    date_column: str | None = None
    date_window_days: int | None = None


class EstimateResponse(BaseModel):
    estimated_bytes: int
    estimated_bytes_human: str
    estimated_cost_usd: float
    sql: str


class TopValue(BaseModel):
    value: str | int | float | bool | None
    count: int
    pct: float


class ExcludedColumn(BaseModel):
    column_name: str
    reason: str


class ColumnProfile(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    completeness_pct: float
    null_count: int
    distinct_count: int
    distinct_pct: float
    min_value: str | int | float | bool | None
    max_value: str | int | float | bool | None
    top_values: list[TopValue] | None
    inferred_logical_type: InferredLogicalType
    coefficient_of_variation: float | None
    quality_flag: QualityFlag


class TableProfilingSummary(BaseModel):
    total_sampled_rows: int
    total_table_rows: int
    estimated_duplicate_rows: int
    estimated_duplicate_pct: float
    overall_density: float


class ProfilingRunResponse(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    executed_at: datetime
    parameters: ProfilingRequest
    sql: str
    table_summary: TableProfilingSummary
    columns: list[ColumnProfile]
    excluded_columns: list[ExcludedColumn]


class NullDistributionPoint(BaseModel):
    period: str
    null_count: int
    null_pct: float
    total_rows: int


class NullDistributionResponse(BaseModel):
    column_name: str
    date_column: str
    granularity: Granularity
    series: list[NullDistributionPoint]


class HistoryColumnSnapshot(BaseModel):
    column_name: str
    completeness_pct: float
    quality_flag: QualityFlag


class ProfilingHistoryRun(BaseModel):
    executed_at: datetime
    executed_by: str
    overall_density: float
    estimated_duplicate_pct: float
    columns: list[HistoryColumnSnapshot]


class ProfilingHistoryResponse(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    runs: list[ProfilingHistoryRun]
