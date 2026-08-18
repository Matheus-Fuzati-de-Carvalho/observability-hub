export interface BucketSummary {
  name: string
  location: string
  storage_class: string
  total_size_bytes: number
  object_count: number
  has_lifecycle_rule: boolean
  time_created: string
  updated: string
}

export interface BucketsListResponse {
  buckets: BucketSummary[]
}

export type MinDaysUnused = 30 | 60 | 90

export type WasteConfidence = 'config_based' | 'usage_confirmed'

export interface WasteCandidate {
  bucket_name: string
  eligible_object_count: number
  eligible_size_bytes: number
  oldest_object_age_days: number
  estimated_savings_usd_month_min: number
  estimated_savings_usd_month_max: number
  usage_confirmed_object_count: number
  usage_confirmed_size_bytes: number
  confidence: WasteConfidence
}

export interface WasteCandidatesResponse {
  project_id: string
  min_days_unused: MinDaysUnused
  candidates: WasteCandidate[]
  savings_disclaimer: string
  usage_check_warning: string | null
}
