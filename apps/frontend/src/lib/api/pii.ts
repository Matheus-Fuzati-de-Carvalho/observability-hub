import { httpClient } from '@/lib/http-client'
import type { PiiEstimateResponse, PiiScanRequest, PiiScanResponse } from '@/types/pii'

export const piiApi = {
  estimate: (projectId: string, datasetId: string, tableId: string, body: PiiScanRequest) =>
    httpClient.post<PiiEstimateResponse>(
      `/api/v1/pii/${projectId}/${datasetId}/${tableId}/estimate`,
      body,
    ),

  run: (projectId: string, datasetId: string, tableId: string, body: PiiScanRequest) =>
    httpClient.post<PiiScanResponse>(`/api/v1/pii/${projectId}/${datasetId}/${tableId}/run`, body),
}
