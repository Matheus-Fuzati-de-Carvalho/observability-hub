from datetime import datetime
from enum import Enum, IntEnum

from pydantic import BaseModel


class MinDaysUnused(IntEnum):
    """IntEnum, não Literal[int,...] — Literal não faz coerção de string
    pra int em parâmetro de query (FastAPI/Pydantic recebem "30" como
    string e Literal exige o tipo exato, sem lax-coercion — resultava em
    422 pra toda chamada com min_days_unused na URL). IntEnum resolve
    porque seus membros aceitam coerção de string na validação."""

    THIRTY = 30
    SIXTY = 60
    NINETY = 90


class UnusedTable(BaseModel):
    dataset_id: str
    table_id: str
    size_bytes: int
    size_human: str
    last_accessed_at: datetime | None
    days_since_last_access: int | None
    estimated_monthly_storage_cost_usd: float


class UnusedTablesResponse(BaseModel):
    project_id: str
    min_days_unused: MinDaysUnused
    lookback_days: int
    tables: list[UnusedTable]
    warning: str | None = None


class PartitionCandidate(BaseModel):
    dataset_id: str
    table_id: str
    size_bytes: int
    size_human: str
    row_count: int | None
    candidate_partition_columns: list[str]
    observed_billed_bytes_30d: int
    observed_cost_usd_30d: float
    estimated_savings_usd_conservative: float | None
    estimated_savings_usd_optimistic: float | None
    savings_disclaimer: str | None


class PartitionCandidatesResponse(BaseModel):
    project_id: str
    lookback_days: int
    candidates: list[PartitionCandidate]
    warning: str | None = None


class BudgetGroupBy(str, Enum):
    TABLE = "table"
    USER = "user"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


class CostGroup(BaseModel):
    key: str
    cost_usd: float
    billed_bytes: int
    job_count: int


class CostlyQuery(BaseModel):
    job_id: str
    principal_email: str
    executed_at: datetime
    billed_bytes: int
    cost_usd: float
    tables: list[str]
    query_text: str | None


class CostProjection(BaseModel):
    days_elapsed: int
    days_in_month: int
    cost_so_far_usd: float
    daily_average_usd: float
    projected_month_total_usd: float


class BudgetResponse(BaseModel):
    project_id: str
    period_start: datetime
    lookback_days: int
    group_by: BudgetGroupBy
    groups: list[CostGroup]
    total_cost_usd: float
    top_queries: list[CostlyQuery]
    projection: CostProjection
    warning: str | None = None
