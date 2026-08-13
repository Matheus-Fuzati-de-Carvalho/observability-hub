import { httpClient } from '@/lib/http-client'
import type { QualityScoreResponse } from '@/types/quality'

export const qualityApi = {
  getScore: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<QualityScoreResponse>(
      `/api/v1/quality/score/${projectId}/${datasetId}/${tableId}`,
    ),
}
