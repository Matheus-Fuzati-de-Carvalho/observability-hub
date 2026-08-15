export type MinDaysUnused = 30 | 60 | 90

export interface UnusedTable {
  dataset_id: string
  table_id: string
  size_bytes: number
  size_human: string
  last_accessed_at: string | null
  days_since_last_access: number | null
  estimated_monthly_storage_cost_usd: number
}

export interface UnusedTablesResponse {
  project_id: string
  min_days_unused: MinDaysUnused
  lookback_days: number
  tables: UnusedTable[]
  warning: string | null
}

export interface PartitionCandidate {
  dataset_id: string
  table_id: string
  size_bytes: number
  size_human: string
  row_count: number | null
  candidate_partition_columns: string[]
  observed_billed_bytes_30d: number
  observed_cost_usd_30d: number
  estimated_savings_usd_conservative: number | null
  estimated_savings_usd_optimistic: number | null
  savings_disclaimer: string | null
}

export interface PartitionCandidatesResponse {
  project_id: string
  lookback_days: number
  candidates: PartitionCandidate[]
  warning: string | null
}

export interface DatasetCost {
  dataset_id: string
  cost_usd: number
  billed_bytes: number
}

export interface CostlyQuery {
  job_id: string
  principal_email: string
  executed_at: string
  billed_bytes: number
  cost_usd: number
  tables: string[]
  query_text: string | null
}

export interface TopSpender {
  principal_email: string
  is_service_account: boolean
  cost_usd: number
  billed_bytes: number
  job_count: number
}

export interface CostProjection {
  days_elapsed: number
  days_in_month: number
  cost_so_far_usd: number
  daily_average_usd: number
  projected_month_total_usd: number
}

export interface BudgetResponse {
  project_id: string
  period_start: string
  lookback_days: number
  by_dataset: DatasetCost[]
  top_queries: CostlyQuery[]
  top_spenders: TopSpender[]
  projection: CostProjection
  warning: string | null
}
