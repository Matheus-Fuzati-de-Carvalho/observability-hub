import { useQuery } from '@tanstack/react-query'
import { catalogApi } from '@/lib/api/catalog'

export function useDatasets(projectId: string | undefined) {
  return useQuery({
    queryKey: ['datasets', projectId],
    queryFn: () => catalogApi.listDatasets(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useTables(projectId: string | undefined, datasetId: string | undefined) {
  return useQuery({
    queryKey: ['tables', projectId, datasetId],
    queryFn: () => catalogApi.listTables(projectId as string, datasetId as string),
    enabled: Boolean(projectId) && Boolean(datasetId),
  })
}

export function useTableDetail(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return useQuery({
    queryKey: ['table-detail', projectId, datasetId, tableId],
    queryFn: () =>
      catalogApi.getTableDetail(projectId as string, datasetId as string, tableId as string),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}
