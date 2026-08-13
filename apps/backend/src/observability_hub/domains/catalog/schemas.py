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
    # True quando project_id é o projeto GCP onde o próprio Hub está rodando
    # (client.project, resolvido via GOOGLE_CLOUD_PROJECT/ADC — ver
    # core/bigquery.py::get_client). Usado pelo frontend pra distinguir
    # "observando a si mesmo" de "observando um projeto de cliente/externo".
    is_native: bool


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
    # Vem de TABLE_STORAGE (mesmo JOIN de size_bytes/row_count) — pode ser
    # null por atraso de propagação de metadados em tabelas recém-criadas.
    last_modified_time: datetime | None
    size_bytes: int | None
    size_gb: float | None
    row_count: int | None
    column_count: int
    is_partitioned: bool
    partition_column: str | None
    is_clustered: bool
    clustering_columns: list[str]
    location: str
    # "{coluna} (DAY)" etc — None quando a tabela não é particionada (ver
    # repository._partition_type_label).
    partition_type: str | None = None
    # Min/max/contagem distinct real da coluna de partição (repository.
    # get_partition_stats) — None quando a tabela não é particionada.
    min_partition: str | None = None
    max_partition: str | None = None
    partition_count: int | None = None


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


class PartitionRow(BaseModel):
    value: str
    row_count: int


class TablePartitionsResponse(BaseModel):
    table_id: str
    partition_column: str
    partition_type: str
    total_partitions: int
    partitions: list[PartitionRow]


class SearchMode(str, Enum):
    EXACT = "exact"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"


class DatasetWithMatch(BaseModel):
    dataset_id: str
    table_id: str
    table_type: str
    last_modified_time: datetime | None
    # client.get_table().num_rows — mesma chamada já feita pra
    # last_modified_time (core.bigquery.get_tables_metadata), sem query BQ
    # extra. None em VIEW/EXTERNAL ou se a tabela sumiu entre a busca e a
    # chamada (race, mesmo comportamento de TableSummary.row_count).
    row_count: int | None


class DatasetWithoutMatch(BaseModel):
    dataset_id: str
    # "prefix_exists": dataset tem outra tabela com o mesmo prefixo
    # (repository.derive_search_prefix) mas não a buscada — modes exact/
    # contains. "no_match": nenhuma tabela do dataset contém o termo —
    # mode not_contains (ver service.search_tables).
    reason: str
    latest_partition: str | None = None


class TableSearchResponse(BaseModel):
    query: str
    mode: SearchMode
    project_id: str
    datasets_with_match: list[DatasetWithMatch]
    datasets_without_match: list[DatasetWithoutMatch]
