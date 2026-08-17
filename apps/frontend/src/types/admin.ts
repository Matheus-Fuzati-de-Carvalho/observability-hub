export interface HubUser {
  email: string
  is_admin: boolean
  // "*" (literal) libera qualquer project_id que a service account de
  // runtime alcançar.
  allowed_projects: string[]
  created_at: string
  updated_at: string
  updated_by: string
}

export interface HubUsersListResponse {
  users: HubUser[]
}

export interface UpsertHubUserRequest {
  is_admin: boolean
  allowed_projects: string[]
}

export interface HubProject {
  project_id: string
  // Libera o projeto pra QUALQUER usuário do Hub, inclusive quem ainda
  // não tem doc em hub_users (usuário futuro) — eixo independente de
  // allowed_projects de cada usuário.
  is_public: boolean
  created_at: string
  updated_at: string
  updated_by: string
}

export interface HubProjectsListResponse {
  projects: HubProject[]
}

export interface UpsertHubProjectRequest {
  is_public: boolean
}

export type ProjectAccessGrantedVia = 'explicit' | 'wildcard'

export interface ProjectAccessGrant {
  email: string
  is_admin: boolean
  granted_via: ProjectAccessGrantedVia
}

export interface ProjectUsersResponse {
  project_id: string
  is_public: boolean
  users: ProjectAccessGrant[]
}

export type AccessRequestStatus = 'pending' | 'approved' | 'denied'

export interface AccessRequest {
  request_id: string
  email: string
  project_id: string
  status: AccessRequestStatus
  requested_at: string
  resolved_at: string | null
  resolved_by: string | null
}

export interface AccessRequestsListResponse {
  requests: AccessRequest[]
}

export interface CreateAccessRequestsRequest {
  project_ids: string[]
}
