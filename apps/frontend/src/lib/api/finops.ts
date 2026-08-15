import { httpClient } from '@/lib/http-client'
import type {
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
}
