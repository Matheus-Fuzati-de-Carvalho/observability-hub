import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/lib/api/admin'
import type { UpsertHubUserRequest } from '@/types/admin'

export const ADMIN_USERS_QUERY_KEY = ['admin-users']

export function useHubUsers() {
  return useQuery({
    queryKey: ADMIN_USERS_QUERY_KEY,
    queryFn: adminApi.listUsers,
  })
}

export function useUpsertHubUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ email, request }: { email: string; request: UpsertHubUserRequest }) =>
      adminApi.upsertUser(email, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY })
    },
  })
}

export function useDeleteHubUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (email: string) => adminApi.removeUser(email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY })
    },
  })
}
