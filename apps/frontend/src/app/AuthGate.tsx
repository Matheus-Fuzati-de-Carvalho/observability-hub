import { type ReactNode, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const AUTH_STORAGE_KEY = 'observability-hub:authenticated'
const HARDCODED_PASSWORD = 'senha123'

function isAuthenticated(): boolean {
  try {
    return sessionStorage.getItem(AUTH_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function persistAuthenticated(): void {
  try {
    sessionStorage.setItem(AUTH_STORAGE_KEY, 'true')
  } catch {
    // sessionStorage indisponível (modo privado, etc.) — não é crítico, só
    // volta a pedir a senha no próximo reload.
  }
}

export function AuthGate({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(isAuthenticated)
  const [password, setPassword] = useState('')
  const [showError, setShowError] = useState(false)

  if (authenticated) return <>{children}</>

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (password === HARDCODED_PASSWORD) {
      persistAuthenticated()
      setAuthenticated(true)
    } else {
      setShowError(true)
    }
  }

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

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <Label
            htmlFor="password"
            className="text-xs font-semibold text-muted-foreground uppercase"
          >
            Senha
          </Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              setShowError(false)
            }}
            autoFocus
          />

          <Button type="submit" disabled={!password}>
            Entrar
          </Button>

          {showError && <p className="text-sm text-status-error">Senha incorreta</p>}
        </form>
      </div>
    </div>
  )
}
