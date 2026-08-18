import { httpClient } from '@/lib/http-client'
import type { BucketsListResponse, MinDaysUnused, WasteCandidatesResponse } from '@/types/storage'

export const storageApi = {
  getBuckets: (projectId: string) =>
    httpClient.get<BucketsListResponse>(`/api/v1/storage/${projectId}/buckets`),

  getWasteCandidates: (projectId: string, minDaysUnused: MinDaysUnused = 60) =>
    httpClient.get<WasteCandidatesResponse>(
      `/api/v1/storage/${projectId}/waste-candidates?min_days_unused=${minDaysUnused}`,
    ),
}
