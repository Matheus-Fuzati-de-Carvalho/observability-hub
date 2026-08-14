from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AccessType = Literal["read", "write"]


class TableAccessEntry(BaseModel):
    principal_email: str
    is_service_account: bool
    last_accessed_at: datetime
    access_count: int
    access_types: list[AccessType]


class TableAccessResponse(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    lookback_days: int
    users: list[TableAccessEntry]
    warning: str | None = None
