import { httpClient } from '@/lib/http-client'
import type { TableAccessResponse } from '@/types/access'

export const accessApi = {
  getTableAccess: (projectId: string, datasetId: string, tableId: string, limit = 20) =>
    httpClient.get<TableAccessResponse>(
      `/api/v1/access/${projectId}/${datasetId}/${tableId}?limit=${limit}`,
    ),
}
