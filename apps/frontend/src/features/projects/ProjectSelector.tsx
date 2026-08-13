import { CheckCircle2, Cloud, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useValidateProject } from '@/features/projects/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { clearLastProjectId, getLastProjectId, setLastProjectId } from '@/hooks/useLastProject'
import { cn } from '@/lib/utils'

export function ProjectSelector() {
  const { projectId, setProjectId } = useProjectContext()
  const [input, setInput] = useState('')
  const [submittedProjectId, setSubmittedProjectId] = useState<string | undefined>(undefined)
  const [isRestoring, setIsRestoring] = useState(false)

  const validateQuery = useValidateProject(submittedProjectId)

  // Restaura e revalida automaticamente o projeto salvo no localStorage ao
  // carregar a página (F5) — só no mount, sem o usuário precisar digitar de
  // novo.
  useEffect(() => {
    const lastProjectId = getLastProjectId()
    if (lastProjectId) {
      setInput(lastProjectId)
      setSubmittedProjectId(lastProjectId)
      setIsRestoring(true)
    }
  }, [])

  useEffect(() => {
    if (validateQuery.data?.accessible && submittedProjectId) {
      setProjectId(submittedProjectId)
      setLastProjectId(submittedProjectId)
      setIsRestoring(false)
    }
  }, [validateQuery.data, submittedProjectId, setProjectId])

  // Projeto restaurado do localStorage perdeu o acesso (ex: revogado desde
  // a última visita) — limpa o storage e volta pro campo vazio em vez de
  // deixar um project_id inválido preenchido.
  useEffect(() => {
    if (isRestoring && (validateQuery.isError || validateQuery.data?.accessible === false)) {
      clearLastProjectId()
      setInput('')
      setSubmittedProjectId(undefined)
      setIsRestoring(false)
    }
  }, [isRestoring, validateQuery.isError, validateQuery.data])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setIsRestoring(false)
    if (input.trim()) setSubmittedProjectId(input.trim())
  }

  const showError = validateQuery.isError || validateQuery.data?.accessible === false
  const errorMessage =
    validateQuery.error instanceof Error
      ? validateQuery.error.message
      : 'Projeto sem acesso ou inexistente.'

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Cloud size={16} />
        <span>GCP Project:</span>
      </div>
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="observability-hub-dev"
        className="h-7 w-56 text-sm"
      />
      <Button type="submit" size="sm" disabled={!input.trim() || validateQuery.isFetching}>
        {validateQuery.isFetching ? 'Validando…' : 'Validar'}
      </Button>
      {validateQuery.data?.accessible && submittedProjectId === projectId && (
        <>
          <CheckCircle2 size={16} className="text-status-ok" aria-label="Projeto acessível" />
          <Tooltip>
            <TooltipTrigger
              render={
                <Badge
                  variant="outline"
                  className={cn(
                    validateQuery.data.is_native
                      ? 'border-status-ok/30 bg-status-ok/10 text-status-ok'
                      : 'border-status-warn/30 bg-status-warn/10 text-status-warn',
                  )}
                />
              }
            >
              {validateQuery.data.is_native ? 'Projeto nativo' : 'Projeto externo'}
            </TooltipTrigger>
            <TooltipContent>
              Nativo = projeto onde o Hub está hospedado. Externo = projeto de cliente ou outro
              ambiente.
            </TooltipContent>
          </Tooltip>
        </>
      )}
      {showError && (
        <span title={errorMessage}>
          <XCircle size={16} className="text-status-error" aria-label={errorMessage} />
        </span>
      )}
    </form>
  )
}
