from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TableType(str, Enum):
    """Valores expostos pela API. A INFORMATION_SCHEMA.TABLES do BigQuery usa
    "BASE TABLE" e "MATERIALIZED VIEW" (com espaço) — o repository normaliza
    para estes valores antes de popular os schemas de response."""

    TABLE = "TABLE"
    VIEW = "VIEW"
    EXTERNAL = "EXTERNAL"
    MATERIALIZED_VIEW = "MATERIALIZED_VIEW"


class ProjectValidateResponse(BaseModel):
    project_id: str
    accessible: bool
    available_regions: list[str]
    total_datasets: int


class DatasetSummary(BaseModel):
    dataset_id: str
    location: str
    creation_time: datetime
    last_modified_time: datetime
    total_tables: int
    total_views: int
    total_size_bytes: int
    total_size_gb: float
    total_rows: int


class DatasetsListResponse(BaseModel):
    project_id: str
    evaluated_at: datetime
    total_datasets: int
    regions_found: list[str]
    datasets: list[DatasetSummary]


class TableSummary(BaseModel):
    table_id: str
    table_type: str
    creation_time: datetime
    last_modified_time: datetime
    size_bytes: int | None
    size_gb: float | None
    row_count: int | None
    column_count: int
    is_partitioned: bool
    partition_column: str | None
    is_clustered: bool
    clustering_columns: list[str]
    location: str


class TablesListResponse(BaseModel):
    project_id: str
    dataset_id: str
    location: str
    total_tables: int
    tables: list[TableSummary]


class ColumnDetail(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    description: str | None = None


class TableDetail(TableSummary):
    columns: list[ColumnDetail]
    labels: dict[str, str]
    description: str | None = None
