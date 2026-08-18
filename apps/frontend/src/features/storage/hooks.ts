import { useQuery } from '@tanstack/react-query'
import { storageApi } from '@/lib/api/storage'

export function useBuckets(projectId: string | undefined) {
  return useQuery({
    queryKey: ['storage', 'buckets', projectId],
    queryFn: () => storageApi.getBuckets(projectId as string),
    enabled: Boolean(projectId),
  })
}
