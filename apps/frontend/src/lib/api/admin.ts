import { httpClient } from '@/lib/http-client'
import type {
  AccessRequest,
  AccessRequestStatus,
  AccessRequestsListResponse,
  HubProject,
  HubProjectsListResponse,
  HubUser,
  HubUsersListResponse,
  ProjectUsersResponse,
  UpsertHubProjectRequest,
  UpsertHubUserRequest,
} from '@/types/admin'

export const adminApi = {
  listUsers: () => httpClient.get<HubUsersListResponse>('/api/v1/admin/users'),

  upsertUser: (email: string, request: UpsertHubUserRequest) =>
    httpClient.put<HubUser>(`/api/v1/admin/users/${encodeURIComponent(email)}`, request),

  removeUser: (email: string) =>
    httpClient.delete<undefined>(`/api/v1/admin/users/${encodeURIComponent(email)}`),

  listProjects: () => httpClient.get<HubProjectsListResponse>('/api/v1/admin/projects'),

  upsertProject: (projectId: string, request: UpsertHubProjectRequest) =>
    httpClient.put<HubProject>(`/api/v1/admin/projects/${encodeURIComponent(projectId)}`, request),

  getProjectUsers: (projectId: string) =>
    httpClient.get<ProjectUsersResponse>(
      `/api/v1/admin/projects/${encodeURIComponent(projectId)}/users`,
    ),

  grantProjectAccess: (projectId: string, email: string) =>
    httpClient.post<HubUser>(
      `/api/v1/admin/projects/${encodeURIComponent(projectId)}/users/${encodeURIComponent(email)}`,
    ),

  revokeProjectAccess: (projectId: string, email: string) =>
    httpClient.delete<undefined>(
      `/api/v1/admin/projects/${encodeURIComponent(projectId)}/users/${encodeURIComponent(email)}`,
    ),

  listAccessRequests: (status?: AccessRequestStatus) =>
    httpClient.get<AccessRequestsListResponse>(
      `/api/v1/admin/access-requests${status ? `?status=${status}` : ''}`,
    ),

  approveAccessRequest: (requestId: string) =>
    httpClient.post<AccessRequest>(
      `/api/v1/admin/access-requests/${encodeURIComponent(requestId)}/approve`,
    ),

  denyAccessRequest: (requestId: string) =>
    httpClient.post<AccessRequest>(
      `/api/v1/admin/access-requests/${encodeURIComponent(requestId)}/deny`,
    ),
}
