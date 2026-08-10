export interface ProjectValidateResponse {
  project_id: string
  accessible: boolean
  available_regions: string[]
  total_datasets: number
}

export interface ApiErrorBody {
  error: string
  message: string
  fix?: string
  available_date_columns?: string[]
}
