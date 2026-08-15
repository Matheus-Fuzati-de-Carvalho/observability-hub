export interface ProjectValidateResponse {
  project_id: string
  accessible: boolean
  available_regions: string[]
  total_datasets: number
  is_native: boolean
}

export interface ApiErrorBody {
  error: string
  message: string
  fix?: string[]
  available_date_columns?: string[]
}
