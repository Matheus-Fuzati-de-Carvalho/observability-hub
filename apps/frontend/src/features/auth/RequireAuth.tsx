import { Navigate, Outlet } from 'react-router-dom'
import { useCurrentUser } from '@/features/auth/hooks'

export function RequireAuth() {
  const userQuery = useCurrentUser()

  if (userQuery.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        Carregando…
      </div>
    )
  }

  if (userQuery.isError || !userQuery.data) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
