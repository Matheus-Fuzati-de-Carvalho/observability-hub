import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AUTH_ME_QUERY_KEY } from '@/features/auth/hooks'
import { authApi } from '@/lib/api/auth'
import { ApiError } from '@/lib/http-client'

export function AuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  // StrictMode monta o efeito duas vezes em dev — o code do Google só pode
  // ser trocado uma vez (reuso é rejeitado pelo Google), então a segunda
  // chamada precisa ser evitada, não só a UI duplicada.
  const hasRun = useRef(false)

  useEffect(() => {
    if (hasRun.current) return
    hasRun.current = true

    const code = searchParams.get('code')
    const state = searchParams.get('state')
    if (!code || !state) {
      navigate('/login', { replace: true, state: { error: 'Callback do Google sem code/state.' } })
      return
    }

    authApi
      .callback(code, state)
      .then(() => {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_QUERY_KEY })
        navigate('/', { replace: true })
      })
      .catch((err) => {
        const message = err instanceof ApiError ? err.message : 'Falha ao autenticar com o Google.'
        navigate('/login', { replace: true, state: { error: message } })
      })
  }, [searchParams, navigate, queryClient])

  return (
    <div className="flex h-screen items-center justify-center text-muted-foreground">
      Autenticando…
    </div>
  )
}
