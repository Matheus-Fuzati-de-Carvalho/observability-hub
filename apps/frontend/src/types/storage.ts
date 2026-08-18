export interface BucketSummary {
  name: string
  location: string
  storage_class: string
  total_size_bytes: number
  object_count: number
  has_lifecycle_rule: boolean
}

export interface BucketsListResponse {
  buckets: BucketSummary[]
}

export interface BucketFreshnessResponse {
  bucket_name: string
  last_modified: string | null
  warning: string | null
}
