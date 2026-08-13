import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { historyApi } from '@/lib/api/history'

export const HISTORY_QUERY_KEY = ['history']

export function useHistory() {
  return useQuery({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: historyApi.get,
  })
}

interface RecordTableViewVariables {
  projectId: string
  datasetId: string
  tableId: string
}

export function useRecordTableView() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId }: RecordTableViewVariables) =>
      historyApi.recordTableView(projectId, datasetId, tableId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: HISTORY_QUERY_KEY }),
  })
}

interface RecordSearchVariables {
  query: string
  mode: string
  projectId: string
}

export function useRecordSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ query, mode, projectId }: RecordSearchVariables) =>
      historyApi.recordSearch(query, mode, projectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: HISTORY_QUERY_KEY }),
  })
}
