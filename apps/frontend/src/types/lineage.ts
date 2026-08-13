export interface TableRef {
  project_id: string
  dataset_id: string
  table_id: string
}

export interface LineageResponse {
  project_id: string
  dataset_id: string
  table_id: string
  upstream: TableRef[]
  downstream: TableRef[]
  lookback_days: number
  warning: string | null
}

export interface OrphanTable {
  dataset_id: string
  table_id: string
}

export interface OrphansResponse {
  project_id: string
  orphans: OrphanTable[]
  lookback_days: number
  warning: string | null
}
