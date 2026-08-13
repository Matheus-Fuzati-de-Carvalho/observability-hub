import { httpClient } from '@/lib/http-client'
import type {
  DatasetsListResponse,
  SearchMode,
  TableDetail,
  TablePartitionsResponse,
  TableSearchResponse,
  TablesListResponse,
} from '@/types/catalog'

export const catalogApi = {
  listDatasets: (projectId: string) =>
    httpClient.get<DatasetsListResponse>(`/api/v1/catalog/${projectId}/datasets`),

  listTables: (projectId: string, datasetId: string) =>
    httpClient.get<TablesListResponse>(`/api/v1/catalog/${projectId}/datasets/${datasetId}/tables`),

  getTableDetail: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<TableDetail>(
      `/api/v1/catalog/${projectId}/datasets/${datasetId}/tables/${tableId}`,
    ),

  getTablePartitions: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<TablePartitionsResponse>(
      `/api/v1/catalog/${projectId}/datasets/${datasetId}/tables/${tableId}/partitions`,
    ),

  searchTables: (projectId: string, q: string, mode: SearchMode) => {
    const params = new URLSearchParams({ q, mode })
    return httpClient.get<TableSearchResponse>(
      `/api/v1/catalog/${projectId}/search?${params.toString()}`,
    )
  },
}
