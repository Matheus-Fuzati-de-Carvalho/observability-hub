export interface TableViewEvent {
  project_id: string
  dataset_id: string
  table_id: string
  viewed_at: string
}

export interface SearchEvent {
  query: string
  mode: string
  project_id: string
  searched_at: string
}

export interface HistoryResponse {
  recent_tables: TableViewEvent[]
  recent_searches: SearchEvent[]
}
