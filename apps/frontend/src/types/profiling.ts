export type UniquenessMethod = 'approx' | 'exact'

export type InferredLogicalType =
  | 'id'
  | 'categorical'
  | 'email'
  | 'date_string'
  | 'numeric_string'
  | 'boolean'
  | 'free_text'
  | 'numeric'
  | 'date'
  | 'timestamp'
  | 'unknown'

export type QualityFlag = 'ok' | 'warning' | 'critical'

export interface ProfilingRequest {
  sample_percent: number
  uniqueness_method: UniquenessMethod
  date_column: string | null
  date_window_days: number | null
}

export interface EstimateResponse {
  estimated_bytes: number
  estimated_bytes_human: string
  estimated_cost_usd: number
  sql: string
}

export type ScalarValue = string | number | boolean | null

export interface TopValue {
  value: ScalarValue
  count: number
  pct: number
}

export interface ExcludedColumn {
  column_name: string
  reason: string
}

export interface ColumnProfile {
  column_name: string
  data_type: string
  is_nullable: boolean
  completeness_pct: number
  null_count: number
  distinct_count: number
  distinct_pct: number
  min_value: ScalarValue
  max_value: ScalarValue
  top_values: TopValue[] | null
  inferred_logical_type: InferredLogicalType
  coefficient_of_variation: number | null
  quality_flag: QualityFlag
}

export interface TableProfilingSummary {
  total_sampled_rows: number
  total_table_rows: number
  estimated_duplicate_rows: number
  estimated_duplicate_pct: number
  overall_density: number
}

export interface ProfilingRunResponse {
  project_id: string
  dataset_id: string
  table_id: string
  executed_at: string
  parameters: ProfilingRequest
  sql: string
  table_summary: TableProfilingSummary
  columns: ColumnProfile[]
  excluded_columns: ExcludedColumn[]
}
