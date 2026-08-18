import { httpClient } from '@/lib/http-client'
import type { BucketFreshnessResponse, BucketsListResponse } from '@/types/storage'

export const storageApi = {
  getBuckets: (projectId: string) =>
    httpClient.get<BucketsListResponse>(`/api/v1/storage/${projectId}/buckets`),

  getBucketFreshness: (projectId: string, bucketName: string) =>
    httpClient.get<BucketFreshnessResponse>(
      `/api/v1/storage/${projectId}/buckets/${bucketName}/freshness`,
    ),
}
