from pydantic import BaseModel


class TableRef(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str


class LineageNode(BaseModel):
    id: str
    project_id: str
    dataset_id: str
    table_id: str
    hop_distance: int
    is_root: bool
    access_denied: bool = False


class LineageEdge(BaseModel):
    source: str
    target: str
    job_id: str


class LineageGraphResponse(BaseModel):
    root: TableRef
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    lookback_days: int
    max_hops: int
    truncated: bool
    warning: str | None = None


class OrphanTable(BaseModel):
    dataset_id: str
    table_id: str


class OrphansResponse(BaseModel):
    project_id: str
    orphans: list[OrphanTable]
    lookback_days: int
    warning: str | None = None
