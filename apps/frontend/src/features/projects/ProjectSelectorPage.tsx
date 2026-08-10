import { CheckCircle2, Cloud, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useValidateProject } from '@/features/projects/hooks'
import { getLastProjectId, setLastProjectId } from '@/hooks/useLastProject'

export function ProjectSelectorPage() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [submittedProjectId, setSubmittedProjectId] = useState<string | undefined>(undefined)

  const validateQuery = useValidateProject(submittedProjectId)

  useEffect(() => {
    const lastProjectId = getLastProjectId()
    if (lastProjectId) setInput(lastProjectId)
  }, [])

  useEffect(() => {
    if (validateQuery.data?.accessible && submittedProjectId) {
      setLastProjectId(submittedProjectId)
      navigate(`/p/${submittedProjectId}`)
    }
  }, [validateQuery.data, submittedProjectId, navigate])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (input.trim()) setSubmittedProjectId(input.trim())
  }

  const showError = validateQuery.isError || validateQuery.data?.accessible === false

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8">
        <div className="mb-6 flex items-center gap-3">
          <span className="h-8 w-0.5 bg-primary" />
          <div>
            <h1 className="text-2xl font-bold">Observability Hub</h1>
            <p className="text-sm text-muted-foreground">dp6</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label
            htmlFor="project-id"
            className="text-xs font-semibold text-muted-foreground uppercase"
          >
            GCP Project ID
          </label>
          <div className="relative">
            <Cloud
              size={16}
              className="absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              id="project-id"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="observability-hub-dev"
              className="pl-9"
              autoFocus
            />
          </div>

          <Button type="submit" disabled={!input.trim() || validateQuery.isFetching}>
            {validateQuery.isFetching ? 'Validando…' : 'Validar acesso'}
          </Button>

          {validateQuery.data?.accessible && (
            <p className="flex items-center gap-2 text-sm text-status-ok">
              <CheckCircle2 size={16} />
              Acessível — {validateQuery.data.total_datasets} datasets encontrados.
            </p>
          )}

          {showError && (
            <p className="flex items-center gap-2 text-sm text-status-error">
              <XCircle size={16} />
              {validateQuery.error instanceof Error
                ? validateQuery.error.message
                : 'Projeto sem acesso ou inexistente.'}
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
