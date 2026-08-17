import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useCreateAccessRequests } from '@/features/admin/hooks'
import { ProjectChipEditor } from '@/features/admin/ProjectChipEditor'
import { ApiError } from '@/lib/http-client'

interface RequestAccessDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  // Pré-preenche o chip inicial quando aberto a partir do erro "sem
  // acesso" do ProjectSelector — poupa o usuário de digitar de novo o
  // project_id que acabou de tentar (e falhou).
  initialProjectId?: string
}

export function RequestAccessDialog({
  open,
  onOpenChange,
  initialProjectId,
}: RequestAccessDialogProps) {
  const [projectIds, setProjectIds] = useState<string[]>([])
  const [submitted, setSubmitted] = useState(false)
  const createMutation = useCreateAccessRequests()

  // Reset ao abrir — mesmo motivo de todo outro dialog deste domínio
  // (mutations do TanStack Query não limpam sozinhas).
  // biome-ignore lint/correctness/useExhaustiveDependencies: ver comentário acima
  useEffect(() => {
    if (!open) return
    setProjectIds(initialProjectId ? [initialProjectId] : [])
    setSubmitted(false)
    createMutation.reset()
  }, [open, initialProjectId])

  const errorMessage =
    createMutation.error instanceof ApiError
      ? createMutation.error.message
      : createMutation.error instanceof Error
        ? createMutation.error.message
        : null

  function handleSubmit() {
    if (projectIds.length === 0) return
    createMutation.mutate(projectIds, { onSuccess: () => setSubmitted(true) })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Solicitar acesso a projetos</DialogTitle>
          <DialogDescription>
            Um administrador do Hub vai revisar e liberar (ou negar) cada projeto listado.
          </DialogDescription>
        </DialogHeader>

        {submitted ? (
          <p className="text-sm text-status-ok">
            Solicitação enviada — um administrador vai revisar em breve.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            <ProjectChipEditor
              chips={projectIds}
              onChange={setProjectIds}
              placeholder="project-id"
              emptyLabel="Nenhum projeto adicionado ainda."
            />
            {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}
          </div>
        )}

        <DialogFooter>
          {submitted ? (
            <Button onClick={() => onOpenChange(false)}>Fechar</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button
                disabled={createMutation.isPending || projectIds.length === 0}
                onClick={handleSubmit}
              >
                {createMutation.isPending ? 'Enviando…' : 'Solicitar'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
