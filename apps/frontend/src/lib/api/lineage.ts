import { httpClient } from '@/lib/http-client'
import type { LineageGraphResponse, OrphansResponse } from '@/types/lineage'

export const lineageApi = {
  getLineage: (projectId: string, datasetId: string, tableId: string, maxHops = 8) =>
    httpClient.get<LineageGraphResponse>(
      `/api/v1/lineage/${projectId}/${datasetId}/${tableId}?max_hops=${maxHops}`,
    ),

  getOrphans: (projectId: string) =>
    httpClient.get<OrphansResponse>(`/api/v1/lineage/${projectId}/orphans`),
}
