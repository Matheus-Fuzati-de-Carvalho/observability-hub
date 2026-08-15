import { httpClient } from '@/lib/http-client'
import type {
  BudgetResponse,
  MinDaysUnused,
  PartitionCandidatesResponse,
  UnusedTablesResponse,
} from '@/types/finops'

export const finopsApi = {
  getUnusedTables: (projectId: string, minDaysUnused: MinDaysUnused = 30) =>
    httpClient.get<UnusedTablesResponse>(
      `/api/v1/finops/${projectId}/unused-tables?min_days_unused=${minDaysUnused}`,
    ),

  getPartitionCandidates: (projectId: string) =>
    httpClient.get<PartitionCandidatesResponse>(`/api/v1/finops/${projectId}/partition-candidates`),

  getBudget: (projectId: string, limit = 10) =>
    httpClient.get<BudgetResponse>(`/api/v1/finops/${projectId}/budget?limit=${limit}`),
}
