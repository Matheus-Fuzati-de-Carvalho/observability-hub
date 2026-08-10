import { httpClient } from '@/lib/http-client'
import type { ProjectValidateResponse } from '@/types/projects'

export const projectsApi = {
  validate: (projectId: string) =>
    httpClient.get<ProjectValidateResponse>(`/api/v1/projects/${projectId}/validate`),
}
