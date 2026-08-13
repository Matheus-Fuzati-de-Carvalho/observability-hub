import { useMutation } from '@tanstack/react-query'
import { profilingApi } from '@/lib/api/profiling'
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
