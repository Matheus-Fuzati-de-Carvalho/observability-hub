import { useQuery } from '@tanstack/react-query'
import { storageApi } from '@/lib/api/storage'

export function useBuckets(projectId: string | undefined) {
  return useQuery({
    queryKey: ['storage', 'buckets', projectId],
    queryFn: () => storageApi.getBuckets(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useBucketFreshness(projectId: string | undefined, bucketName: string | null) {
  return useQuery({
    queryKey: ['storage', 'buckets', projectId, bucketName, 'freshness'],
    queryFn: () => storageApi.getBucketFreshness(projectId as string, bucketName as string),
    enabled: Boolean(projectId) && Boolean(bucketName),
  })
}
