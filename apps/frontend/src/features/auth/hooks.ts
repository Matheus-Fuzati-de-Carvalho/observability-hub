import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
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
  const navigate = useNavigate()
  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      // Limpa tudo, não só auth-me — dados de outro usuário não devem
      // sobreviver no cache depois do logout. Navega direto pro /login em
      // vez de confiar só no redirect reativo do RequireAuth (útil como
      // segunda camada, mas o usuário quer o redirect imediato aqui).
      queryClient.clear()
      navigate('/login', { replace: true })
    },
  })
}
