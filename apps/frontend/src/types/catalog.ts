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
