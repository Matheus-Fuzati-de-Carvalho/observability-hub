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

export interface LoginEvent {
  email: string
  logged_in_at: string
}

export interface LoginCountBucket {
  // "2026-08-17" (dia), "2026-W33" (semana ISO) ou "2026-08" (mês).
  period: string
  login_count: number
  unique_users: number
}

export interface LoginAnalyticsResponse {
  daily: LoginCountBucket[]
  weekly: LoginCountBucket[]
  monthly: LoginCountBucket[]
  recent_events: LoginEvent[]
}

export interface FavoriteEntry {
  project_id: string
  dataset_id: string
  table_id: string | null
  nickname: string | null
  owner_email: string
  added_at: string
}

export interface FavoritesAnalyticsResponse {
  favorites: FavoriteEntry[]
}

export interface ProfilingRunEntry {
  project_id: string
  dataset_id: string
  table_id: string
  executed_by: string
  executed_at: string
  overall_density: number
  estimated_duplicate_pct: number
}

export interface ProfilingActivityResponse {
  runs: ProfilingRunEntry[]
}

export interface AccessRequestMonthBucket {
  period: string
  total: number
  approved: number
  denied: number
  pending: number
}

export interface ProjectRequestCount {
  project_id: string
  request_count: number
}

export interface AccessRequestAnalyticsResponse {
  monthly: AccessRequestMonthBucket[]
  top_projects: ProjectRequestCount[]
  approval_rate: number | null
}

export interface TableViewEntry {
  project_id: string
  dataset_id: string
  table_id: string
  owner_email: string
  viewed_at: string
}

export interface SearchEntry {
  query: string
  mode: string
  project_id: string
  owner_email: string
  searched_at: string
}

export interface NavigationAnalyticsResponse {
  table_views: TableViewEntry[]
  searches: SearchEntry[]
}

export interface PiiScanEntry {
  project_id: string
  dataset_id: string
  table_id: string
  executed_by: string
  executed_at: string
  flagged_columns_count: number
}

export interface PiiScanActivityResponse {
  scans: PiiScanEntry[]
}
