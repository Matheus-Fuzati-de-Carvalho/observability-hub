import { Navigate, Outlet } from 'react-router-dom'
import { useCurrentUser } from '@/features/auth/hooks'

// Gate de UX apenas — a garantia real de autorização é o backend
// (core/auth.py::require_admin, 403 em qualquer chamada de
// /api/v1/admin/*). Isso aqui só evita renderizar a tela pra quem não é
// admin; nunca confiar só nisto para segurança.
export function RequireAdmin() {
  const userQuery = useCurrentUser()

  if (userQuery.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        Carregando…
      </div>
    )
  }

  if (!userQuery.data?.is_admin) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
