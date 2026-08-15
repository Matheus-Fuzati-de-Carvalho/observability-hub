import { useQuery } from '@tanstack/react-query'
import { finopsApi } from '@/lib/api/finops'
import type { MinDaysUnused } from '@/types/finops'

export function useUnusedTables(projectId: string | undefined, minDaysUnused: MinDaysUnused = 30) {
  return useQuery({
    queryKey: ['finops-unused-tables', projectId, minDaysUnused],
    queryFn: () => finopsApi.getUnusedTables(projectId as string, minDaysUnused),
    enabled: Boolean(projectId),
  })
}

export function usePartitionCandidates(projectId: string | undefined) {
  return useQuery({
    queryKey: ['finops-partition-candidates', projectId],
    queryFn: () => finopsApi.getPartitionCandidates(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useBudget(projectId: string | undefined, limit = 10) {
  return useQuery({
    queryKey: ['finops-budget', projectId, limit],
    queryFn: () => finopsApi.getBudget(projectId as string, limit),
    enabled: Boolean(projectId),
  })
}
