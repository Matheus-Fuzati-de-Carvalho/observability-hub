from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class SLAStatus(str, Enum):
    """Ordem crescente de severidade — usada para calcular worst_status."""

    OK = "ok"
    WARNING_12_24 = "warning_12_24"
    WARNING_24_48 = "warning_24_48"
    WARNING_48_7D = "warning_48_7d"
    WARNING_7D_1M = "warning_7d_1m"
    STALE = "stale"


class FreshnessCounts(BaseModel):
    total_tables: int
    ok: int
    warning_12_24: int
    warning_24_48: int
    warning_48_7d: int
    warning_7d_1m: int
    stale: int


class DatasetFreshnessSummary(FreshnessCounts):
    dataset_id: str
    location: str
    worst_status: SLAStatus | None


class FreshnessProjectResponse(BaseModel):
    project_id: str
    evaluated_at: datetime
    datasets: list[DatasetFreshnessSummary]


class TableFreshness(BaseModel):
    table_id: str
    table_type: str
    # Vem de TABLE_STORAGE — pode ser null se os metadados de storage ainda
    # não propagaram para uma tabela recém-criada (mesmo caso já visto em
    # catalog.TableSummary).
    last_modified_time: datetime | None
    hours_since_update: float | None
    sla_status: SLAStatus | None
    size_bytes: int | None
    row_count: int | None


class FreshnessDatasetResponse(BaseModel):
    project_id: str
    dataset_id: str
    location: str
    evaluated_at: datetime
    summary: FreshnessCounts
    tables: list[TableFreshness]
