from pydantic import BaseModel


class TableRef(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str


class LineageResponse(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    upstream: list[TableRef]
    downstream: list[TableRef]
    lookback_days: int
    warning: str | None = None


class OrphanTable(BaseModel):
    dataset_id: str
    table_id: str


class OrphansResponse(BaseModel):
    project_id: str
    orphans: list[OrphanTable]
    lookback_days: int
    warning: str | None = None
