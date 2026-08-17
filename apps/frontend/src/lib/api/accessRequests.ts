import { httpClient } from '@/lib/http-client'
import type { AccessRequestsListResponse, CreateAccessRequestsRequest } from '@/types/admin'

// Não é /admin/... — qualquer usuário autenticado pede acesso pra si
// mesmo, ver apps/backend/.../api/v1/access_requests.py.
export const accessRequestsApi = {
  create: (projectIds: string[]) =>
    httpClient.post<AccessRequestsListResponse>('/api/v1/access-requests', {
      project_ids: projectIds,
    } satisfies CreateAccessRequestsRequest),
}
