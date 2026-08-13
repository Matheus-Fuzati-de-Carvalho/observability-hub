import { httpClient } from '@/lib/http-client'
import type { LineageResponse, OrphansResponse } from '@/types/lineage'

export const lineageApi = {
  getLineage: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<LineageResponse>(`/api/v1/lineage/${projectId}/${datasetId}/${tableId}`),

  getOrphans: (projectId: string) =>
    httpClient.get<OrphansResponse>(`/api/v1/lineage/${projectId}/orphans`),
}
