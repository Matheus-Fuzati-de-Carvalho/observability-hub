import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { profilingApi } from '@/lib/api/profiling'
import { qualityApi } from '@/lib/api/quality'
import type { ProfilingRequest } from '@/types/profiling'

interface ProfilingTarget {
  projectId: string
  datasetId: string
  tableId: string
}

export function useEstimateProfiling() {
  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId, ...body }: ProfilingTarget & ProfilingRequest) =>
      profilingApi.estimate(projectId, datasetId, tableId, body),
  })
}

export function useRunProfiling() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId, ...body }: ProfilingTarget & ProfilingRequest) =>
      profilingApi.run(projectId, datasetId, tableId, body),
    // Cada run grava um novo ponto no histórico (backend) — invalida a
    // query da aba Histórico pra ela aparecer sem precisar fechar/reabrir
    // o dialog.
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['quality-history', variables.projectId, variables.datasetId, variables.tableId],
      })
    },
  })
}

export function useQualityHistory(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return useQuery({
    queryKey: ['quality-history', projectId, datasetId, tableId],
    queryFn: () =>
      qualityApi.getHistory(projectId as string, datasetId as string, tableId as string),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}
