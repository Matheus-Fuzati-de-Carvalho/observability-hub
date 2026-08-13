import { useMutation, useQueries } from '@tanstack/react-query'
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
  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId, ...body }: ProfilingTarget & ProfilingRequest) =>
      profilingApi.run(projectId, datasetId, tableId, body),
  })
}

// Uma request por tabela em paralelo (useQueries, não useQuery) — a lista de
// ativos renderiza N linhas de uma vez, uma única query com N tabelas exigiria
// um endpoint em lote que não existe ainda.
export function useQualityScores(projectId: string, datasetId: string, tableIds: string[]) {
  return useQueries({
    queries: tableIds.map((tableId) => ({
      queryKey: ['quality-score', projectId, datasetId, tableId],
      queryFn: () => qualityApi.getScore(projectId, datasetId, tableId),
      staleTime: 60_000,
    })),
  })
}
