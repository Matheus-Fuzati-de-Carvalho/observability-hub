export type TableType = 'TABLE' | 'VIEW' | 'EXTERNAL' | 'MATERIALIZED_VIEW'

export interface DatasetSummary {
  dataset_id: string
  location: string
  creation_time: string
  last_modified_time: string
  total_tables: number
  total_views: number
  total_size_bytes: number
  total_size_gb: number
  total_rows: number
}

export interface DatasetsListResponse {
  project_id: string
  evaluated_at: string
  total_datasets: number
  regions_found: string[]
  datasets: DatasetSummary[]
}

export interface TableSummary {
  table_id: string
  table_type: TableType
  creation_time: string
  last_modified_time: string | null
  size_bytes: number | null
  size_gb: number | null
  row_count: number | null
  column_count: number
  is_partitioned: boolean
  partition_column: string | null
  is_clustered: boolean
  clustering_columns: string[]
  location: string
  partition_type: string | null
  min_partition: string | null
  max_partition: string | null
  partition_count: number | null
}

export interface TablesListResponse {
  project_id: string
  dataset_id: string
  location: string
  total_tables: number
  tables: TableSummary[]
}

export interface ColumnDetail {
  column_name: string
  data_type: string
  is_nullable: boolean
  description: string | null
}

export interface TableDetail extends TableSummary {
  columns: ColumnDetail[]
  labels: Record<string, string>
  description: string | null
}

export interface PartitionRow {
  value: string
  row_count: number
}

export interface TablePartitionsResponse {
  table_id: string
  partition_column: string
  partition_type: string
  total_partitions: number
  partitions: PartitionRow[]
}

export type SearchMode = 'exact' | 'contains' | 'not_contains'

export interface DatasetWithMatch {
  dataset_id: string
  table_id: string
  table_type: string
  last_modified_time: string | null
  row_count: number | null
}

export interface DatasetWithoutMatch {
  dataset_id: string
  reason: string
  latest_partition: string | null
}

export interface TableSearchResponse {
  query: string
  mode: SearchMode
  project_id: string
  datasets_with_match: DatasetWithMatch[]
  datasets_without_match: DatasetWithoutMatch[]
}
