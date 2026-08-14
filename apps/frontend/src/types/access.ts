export type AccessType = 'read' | 'write'

export interface TableAccessEntry {
  principal_email: string
  is_service_account: boolean
  last_accessed_at: string
  access_count: number
  access_types: AccessType[]
}

export interface TableAccessResponse {
  project_id: string
  dataset_id: string
  table_id: string
  lookback_days: number
  users: TableAccessEntry[]
  warning: string | null
}
