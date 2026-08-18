import { httpClient } from '@/lib/http-client'
import type { BucketsListResponse } from '@/types/storage'

export const storageApi = {
  getBuckets: (projectId: string) =>
    httpClient.get<BucketsListResponse>(`/api/v1/storage/${projectId}/buckets`),
}
