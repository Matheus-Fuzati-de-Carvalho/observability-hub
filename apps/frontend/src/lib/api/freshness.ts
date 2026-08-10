import { httpClient } from '@/lib/http-client'
import type { FreshnessDatasetResponse, FreshnessProjectResponse } from '@/types/freshness'

export const freshnessApi = {
  getProjectFreshness: (projectId: string) =>
    httpClient.get<FreshnessProjectResponse>(`/api/v1/freshness/${projectId}`),

  getDatasetFreshness: (projectId: string, datasetId: string) =>
    httpClient.get<FreshnessDatasetResponse>(
      `/api/v1/freshness/${projectId}/datasets/${datasetId}`,
    ),
}
