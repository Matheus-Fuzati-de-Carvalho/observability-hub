import { httpClient } from '@/lib/http-client'
import type { EstimateResponse, ProfilingRequest, ProfilingRunResponse } from '@/types/profiling'

export const profilingApi = {
  estimate: (projectId: string, datasetId: string, tableId: string, body: ProfilingRequest) =>
    httpClient.post<EstimateResponse>(
      `/api/v1/profiling/${projectId}/${datasetId}/${tableId}/estimate`,
      body,
    ),

  run: (projectId: string, datasetId: string, tableId: string, body: ProfilingRequest) =>
    httpClient.post<ProfilingRunResponse>(
      `/api/v1/profiling/${projectId}/${datasetId}/${tableId}/run`,
      body,
    ),
}
