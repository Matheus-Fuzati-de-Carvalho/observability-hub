import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/lib/api/auth'

export const AUTH_ME_QUERY_KEY = ['auth-me']

export function useCurrentUser() {
  return useQuery({
    queryKey: AUTH_ME_QUERY_KEY,
    queryFn: authApi.me,
    retry: false,
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      // Limpa tudo, não só auth-me — dados de outro usuário não devem
      // sobreviver no cache depois do logout.
      queryClient.clear()
    },
  })
}
