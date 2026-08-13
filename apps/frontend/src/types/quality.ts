export interface ScoreBreakdown {
  completeness: number
  freshness: number
  duplicates: number
  documentation: number
}

export interface QualityScoreResponse {
  project_id: string
  dataset_id: string
  table_id: string
  score: number
  breakdown: ScoreBreakdown
  has_profiling_data: boolean
}
