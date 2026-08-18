import { useQuery } from '@tanstack/react-query'
import { storageApi } from '@/lib/api/storage'
import type { MinDaysUnused } from '@/types/storage'

export function useBuckets(projectId: string | undefined) {
  return useQuery({
    queryKey: ['storage', 'buckets', projectId],
    queryFn: () => storageApi.getBuckets(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useWasteCandidates(
  projectId: string | undefined,
  minDaysUnused: MinDaysUnused = 60,
) {
  return useQuery({
    queryKey: ['storage', 'waste-candidates', projectId, minDaysUnused],
    queryFn: () => storageApi.getWasteCandidates(projectId as string, minDaysUnused),
    enabled: Boolean(projectId),
  })
}
