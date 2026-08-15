import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/lib/http-client'

// Backend em dev roda com minScale=0 no Cloud Run — desliga sozinho quando
// ocioso, e a primeira requisição depois disso pode falhar ("Failed to
// fetch", erro de rede — fetch() rejeita antes de qualquer resposta
// chegar, então nunca vira ApiError) enquanto o container ainda está
// subindo. retry: 1 com backoff padrão (~1s) não sobrevive a um cold
// start de vários segundos. Erros HTTP reais (ApiError) só valem retry se
// forem 5xx — 4xx (401/404/422) não se resolve tentando de novo, só
// atrasa o usuário ver o erro real.
function shouldRetryOnNetworkOrServerError(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && error.status < 500) {
    return false
  }
  return failureCount < 3
}

const retryDelay = (attempt: number) => Math.min(1000 * 2 ** attempt, 8000)

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: shouldRetryOnNetworkOrServerError,
      retryDelay,
    },
    // Sem isso, toda ação disparada por useMutation (favoritar, marcar
    // histórico, estimar/rodar profiling e PII, busca do catálogo,
    // logout) tinha ZERO retry por padrão do TanStack Query — um cold
    // start de alguns segundos vira "Failed to fetch" na hora, sem
    // segunda chance, em qualquer tela que use um botão em vez de uma
    // <Table> carregada por useQuery. Mesma política de retry das
    // queries: seguro aqui porque toda mutation deste app ou é idempotente
    // por natureza (toggle de favorito por add/remove da tripla, dry-run/
    // scan somente-leitura de profiling e PII, busca, logout) ou tem
    // consequência mínima em caso de duplicata rara (um registro a mais
    // no histórico de visualizações).
    mutations: {
      retry: shouldRetryOnNetworkOrServerError,
      retryDelay,
    },
  },
})
