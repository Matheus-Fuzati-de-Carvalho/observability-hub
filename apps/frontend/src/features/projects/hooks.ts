import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '@/lib/api/projects'

export function useValidateProject(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-validate', projectId],
    queryFn: () => projectsApi.validate(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  })
}
