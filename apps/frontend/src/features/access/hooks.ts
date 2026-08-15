import { useQuery } from '@tanstack/react-query'
import { accessApi } from '@/lib/api/access'

export function useTableAccess(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
  limit = 20,
) {
  return useQuery({
    queryKey: ['access', projectId, datasetId, tableId, limit],
    queryFn: () =>
      accessApi.getTableAccess(projectId as string, datasetId as string, tableId as string, limit),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}
