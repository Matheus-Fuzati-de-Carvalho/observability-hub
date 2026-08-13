import { httpClient } from '@/lib/http-client'
import type { HistoryResponse } from '@/types/history'

export const historyApi = {
  get: () => httpClient.get<HistoryResponse>('/api/v1/history'),

  recordTableView: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.post<undefined>('/api/v1/history/table-view', {
      project_id: projectId,
      dataset_id: datasetId,
      table_id: tableId,
    }),

  recordSearch: (query: string, mode: string, projectId: string) =>
    httpClient.post<undefined>('/api/v1/history/search', {
      query,
      mode,
      project_id: projectId,
    }),
}
