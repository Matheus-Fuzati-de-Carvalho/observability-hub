from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MinDaysUnused = Literal[30, 60, 90]


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
