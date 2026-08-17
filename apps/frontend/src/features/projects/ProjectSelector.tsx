import { CheckCircle2, Cloud } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { RequestAccessDialog } from '@/features/admin/RequestAccessDialog'
import { useValidateProject } from '@/features/projects/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { clearLastProjectId, getLastProjectId, setLastProjectId } from '@/hooks/useLastProject'
import { ApiError } from '@/lib/http-client'
import { cn } from '@/lib/utils'

export function ProjectSelector() {
  const { projectId, setProjectId } = useProjectContext()
  const [input, setInput] = useState('')
  const [submittedProjectId, setSubmittedProjectId] = useState<string | undefined>(undefined)
  const [isRestoring, setIsRestoring] = useState(false)
  const [requestAccessOpen, setRequestAccessOpen] = useState(false)

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
  const isNotAuthorized =
    validateQuery.error instanceof ApiError &&
    validateQuery.error.body?.error === 'project_not_authorized'

  return (
    <div className="relative">
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
      </form>

      {/* Painel flutuante em vez de um ícone com tooltip só no hover — o
          erro (principalmente "sem acesso, peça liberação") precisa ser
          visível de cara, não escondido atrás de um hover que ninguém
          tenta. Absolute pra não empurrar a altura fixa do Topbar. */}
      {showError && (
        <div className="absolute top-full left-0 z-50 mt-2 w-96">
          <ApiErrorNotice
            error={validateQuery.error}
            showFix={false}
            action={
              isNotAuthorized
                ? { label: 'Solicitar acesso', onClick: () => setRequestAccessOpen(true) }
                : undefined
            }
          />
        </div>
      )}

      <RequestAccessDialog
        open={requestAccessOpen}
        onOpenChange={setRequestAccessOpen}
        initialProjectId={submittedProjectId}
      />
    </div>
  )
}
