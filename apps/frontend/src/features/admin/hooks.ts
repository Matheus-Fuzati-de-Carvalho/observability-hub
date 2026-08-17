import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCurrentUser } from '@/features/auth/hooks'
import { accessRequestsApi } from '@/lib/api/accessRequests'
import { adminApi } from '@/lib/api/admin'
import type {
  AccessRequestStatus,
  UpsertHubProjectRequest,
  UpsertHubUserRequest,
} from '@/types/admin'

export const ADMIN_USERS_QUERY_KEY = ['admin-users']
export const ADMIN_PROJECTS_QUERY_KEY = ['admin-projects']
export const ADMIN_ACCESS_REQUESTS_QUERY_KEY = ['admin-access-requests']

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
      queryClient.invalidateQueries({ queryKey: ADMIN_PROJECTS_QUERY_KEY })
    },
  })
}

export function useDeleteHubUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (email: string) => adminApi.removeUser(email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ADMIN_PROJECTS_QUERY_KEY })
    },
  })
}

export function useHubProjects() {
  return useQuery({
    queryKey: ADMIN_PROJECTS_QUERY_KEY,
    queryFn: adminApi.listProjects,
  })
}

export function useUpsertHubProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, request }: { projectId: string; request: UpsertHubProjectRequest }) =>
      adminApi.upsertProject(projectId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_PROJECTS_QUERY_KEY })
    },
  })
}

export function useProjectUsers(projectId: string | undefined) {
  return useQuery({
    queryKey: ['admin-project-users', projectId],
    queryFn: () => adminApi.getProjectUsers(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useGrantProjectAccess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, email }: { projectId: string; email: string }) =>
      adminApi.grantProjectAccess(projectId, email),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ['admin-project-users', projectId] })
      queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY })
    },
  })
}

export function useRevokeProjectAccess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, email }: { projectId: string; email: string }) =>
      adminApi.revokeProjectAccess(projectId, email),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ['admin-project-users', projectId] })
      queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY })
    },
  })
}

// enabled: is_admin — o backend 403 pra quem não é admin de qualquer
// forma, mas evita disparar a chamada à toa pra maioria dos usuários
// (só admin vê o badge no Topbar). refetchInterval curto o bastante pra
// o badge de pendentes atualizar sozinho sem precisar de F5, sem
// precisar de websocket.
export function usePendingAccessRequests() {
  const userQuery = useCurrentUser()
  return useQuery({
    queryKey: ADMIN_ACCESS_REQUESTS_QUERY_KEY,
    queryFn: () => adminApi.listAccessRequests('pending'),
    enabled: Boolean(userQuery.data?.is_admin),
    refetchInterval: 60_000,
  })
}

export function useAccessRequests(status?: AccessRequestStatus) {
  return useQuery({
    queryKey: ['admin-access-requests-all', status],
    queryFn: () => adminApi.listAccessRequests(status),
  })
}

export function useApproveAccessRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (requestId: string) => adminApi.approveAccessRequest(requestId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_ACCESS_REQUESTS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ['admin-access-requests-all'] })
      queryClient.invalidateQueries({ queryKey: ADMIN_USERS_QUERY_KEY })
    },
  })
}

export function useDenyAccessRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (requestId: string) => adminApi.denyAccessRequest(requestId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_ACCESS_REQUESTS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ['admin-access-requests-all'] })
    },
  })
}

export function useCreateAccessRequests() {
  return useMutation({
    mutationFn: (projectIds: string[]) => accessRequestsApi.create(projectIds),
  })
}

export function useLoginAnalytics(lookbackDays?: number) {
  return useQuery({
    queryKey: ['admin-login-analytics', lookbackDays],
    queryFn: () => adminApi.getLoginAnalytics(lookbackDays),
  })
}

export function useFavoritesAnalytics() {
  return useQuery({
    queryKey: ['admin-favorites-analytics'],
    queryFn: adminApi.getFavoritesAnalytics,
  })
}

export function useProfilingActivity(limit?: number) {
  return useQuery({
    queryKey: ['admin-profiling-activity', limit],
    queryFn: () => adminApi.getProfilingActivity(limit),
  })
}

export function useAccessRequestAnalytics() {
  return useQuery({
    queryKey: ['admin-access-request-analytics'],
    queryFn: adminApi.getAccessRequestAnalytics,
  })
}

export function useNavigationAnalytics() {
  return useQuery({
    queryKey: ['admin-navigation-analytics'],
    queryFn: adminApi.getNavigationAnalytics,
  })
}

export function usePiiScanActivity(limit?: number) {
  return useQuery({
    queryKey: ['admin-pii-scan-activity', limit],
    queryFn: () => adminApi.getPiiScanActivity(limit),
  })
}
