import { httpClient } from '@/lib/http-client'
import type { ProfilingHistoryResponse } from '@/types/quality'

export const qualityApi = {
  getHistory: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<ProfilingHistoryResponse>(
      `/api/v1/quality/history/${projectId}/${datasetId}/${tableId}`,
    ),
}
