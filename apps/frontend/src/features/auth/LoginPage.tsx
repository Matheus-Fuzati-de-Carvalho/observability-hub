import { LogIn } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { authApi } from '@/lib/api/auth'

export function LoginPage() {
  const location = useLocation()
  const error = (location.state as { error?: string } | null)?.error

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8">
        <div className="mb-6 flex items-center gap-3">
          <span className="dp6-divider h-8 w-0.5 bg-primary" />
          <div>
            <h1 className="text-2xl font-bold">Observability Hub</h1>
            <p className="text-sm text-muted-foreground">dp6</p>
          </div>
        </div>

        <Button className="w-full" onClick={() => window.location.assign(authApi.loginUrl())}>
          <LogIn size={16} />
          Entrar com Google
        </Button>

        {error && <p className="mt-3 text-sm text-status-error">{error}</p>}
      </div>
    </div>
  )
}
