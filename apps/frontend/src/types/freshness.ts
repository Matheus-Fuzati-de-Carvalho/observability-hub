export type SLAStatus =
  | 'ok'
  | 'warning_12_24'
  | 'warning_24_48'
  | 'warning_48_7d'
  | 'warning_7d_1m'
  | 'stale'

export interface FreshnessCounts {
  total_tables: number
  ok: number
  warning_12_24: number
  warning_24_48: number
  warning_48_7d: number
  warning_7d_1m: number
  stale: number
}

export interface DatasetFreshnessSummary extends FreshnessCounts {
  dataset_id: string
  location: string
  worst_status: SLAStatus | null
}

export interface FreshnessProjectResponse {
  project_id: string
  evaluated_at: string
  datasets: DatasetFreshnessSummary[]
}

export interface TableFreshness {
  table_id: string
  table_type: string
  last_modified_time: string | null
  hours_since_update: number | null
  sla_status: SLAStatus | null
  size_bytes: number | null
  row_count: number | null
}

export interface FreshnessDatasetResponse {
  project_id: string
  dataset_id: string
  location: string
  evaluated_at: string
  summary: FreshnessCounts
  tables: TableFreshness[]
}
