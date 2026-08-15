import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/lib/http-client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Backend em dev roda com minScale=0 no Cloud Run — desliga sozinho
      // quando ocioso, e a primeira requisição depois disso pode falhar
      // ("Failed to fetch", erro de rede — fetch() rejeita antes de
      // qualquer resposta chegar, então nunca vira ApiError) enquanto o
      // container ainda está subindo. retry: 1 com backoff padrão (~1s)
      // não sobrevive a um cold start de vários segundos. Erros HTTP reais
      // (ApiError) só valem retry se forem 5xx — 4xx (401/404/422) não se
      // resolve tentando de novo, só atrasa o usuário ver o erro real.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status < 500) {
          return false
        }
        return failureCount < 3
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    },
  },
})
