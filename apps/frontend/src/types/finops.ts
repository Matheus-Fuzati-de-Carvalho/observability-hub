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
