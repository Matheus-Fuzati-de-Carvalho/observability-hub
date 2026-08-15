export interface TableRef {
  project_id: string
  dataset_id: string
  table_id: string
}

export interface LineageNode {
  id: string
  project_id: string
  dataset_id: string
  table_id: string
  hop_distance: number
  is_root: boolean
  access_denied: boolean
}

export interface LineageEdge {
  source: string
  target: string
  job_id: string
}

export interface LineageGraphResponse {
  root: TableRef
  nodes: LineageNode[]
  edges: LineageEdge[]
  lookback_days: number
  max_hops: number
  truncated: boolean
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
