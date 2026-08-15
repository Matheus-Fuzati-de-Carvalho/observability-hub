import { useQuery } from '@tanstack/react-query'
import { lineageApi } from '@/lib/api/lineage'

export function useTableLineage(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
  maxHops = 8,
) {
  return useQuery({
    queryKey: ['lineage', projectId, datasetId, tableId, maxHops],
    queryFn: () =>
      lineageApi.getLineage(projectId as string, datasetId as string, tableId as string, maxHops),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}

export function useOrphans(projectId: string | undefined) {
  return useQuery({
    queryKey: ['orphans', projectId],
    queryFn: () => lineageApi.getOrphans(projectId as string),
    enabled: Boolean(projectId),
  })
}
