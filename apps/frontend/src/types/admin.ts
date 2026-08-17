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
