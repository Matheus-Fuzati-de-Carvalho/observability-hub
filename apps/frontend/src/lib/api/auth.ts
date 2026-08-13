import { API_BASE_URL, httpClient } from '@/lib/http-client'
import type { UserInfo } from '@/types/auth'

export const authApi = {
  me: () => httpClient.get<UserInfo>('/api/v1/auth/me'),

  logout: () => httpClient.post<void>('/api/v1/auth/logout'),

  callback: (code: string, state: string) => {
    const params = new URLSearchParams({ code, state })
    return httpClient.get<{ user: UserInfo }>(`/api/v1/auth/callback?${params.toString()}`)
  },

  // Navegação de página inteira (não fetch) — o browser precisa seguir o
  // redirect 302 do backend pro Google de verdade, não interceptado por JS.
  loginUrl: () => `${API_BASE_URL}/api/v1/auth/login`,
}
