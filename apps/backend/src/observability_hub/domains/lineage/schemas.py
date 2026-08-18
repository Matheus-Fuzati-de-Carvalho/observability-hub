from typing import Literal

from pydantic import BaseModel


class TableRef(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str


class LineageNode(BaseModel):
    id: str
    type: Literal["table", "bucket"] = "table"
    # project_id/dataset_id/table_id preenchidos só quando type="table";
    # bucket_name só quando type="bucket" — nunca os dois ao mesmo tempo.
    # Extensão de 2026-08-18 (bucket como nó, ver docs/specs/storage.md
    # seção 7); antes disso todo nó era implicitamente uma tabela.
    project_id: str | None = None
    dataset_id: str | None = None
    table_id: str | None = None
    bucket_name: str | None = None
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
