import { httpClient } from '@/lib/http-client'
import type { HubUser, HubUsersListResponse, UpsertHubUserRequest } from '@/types/admin'

export const adminApi = {
  listUsers: () => httpClient.get<HubUsersListResponse>('/api/v1/admin/users'),

  upsertUser: (email: string, request: UpsertHubUserRequest) =>
    httpClient.put<HubUser>(`/api/v1/admin/users/${encodeURIComponent(email)}`, request),

  removeUser: (email: string) =>
    httpClient.delete<undefined>(`/api/v1/admin/users/${encodeURIComponent(email)}`),
}
