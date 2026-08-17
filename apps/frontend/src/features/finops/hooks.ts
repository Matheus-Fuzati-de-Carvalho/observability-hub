import { useMutation, useQuery } from '@tanstack/react-query'
import { finopsApi } from '@/lib/api/finops'
import type { BudgetGroupBy, MinDaysUnused } from '@/types/finops'

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

export function useBudget(
  projectId: string | undefined,
  groupBy: BudgetGroupBy = 'table',
  limit = 10,
) {
  return useQuery({
    queryKey: ['finops-budget', projectId, groupBy, limit],
    queryFn: () => finopsApi.getBudget(projectId as string, groupBy, limit),
    enabled: Boolean(projectId),
  })
}

interface ColumnTypeScanVariables {
  projectId: string
  samplePercent: number
  tables: string[]
}

export function useEstimateColumnTypeSuggestions() {
  return useMutation({
    mutationFn: ({ projectId, samplePercent, tables }: ColumnTypeScanVariables) =>
      finopsApi.estimateColumnTypeSuggestions(projectId, samplePercent, tables),
  })
}

export function useRunColumnTypeSuggestions() {
  return useMutation({
    mutationFn: ({ projectId, samplePercent, tables }: ColumnTypeScanVariables) =>
      finopsApi.runColumnTypeSuggestions(projectId, samplePercent, tables),
  })
}
