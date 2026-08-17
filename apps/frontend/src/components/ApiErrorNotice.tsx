import { CircleAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/http-client'

interface ApiErrorNoticeProps {
  error: unknown
  // Botão de ação opcional depois da mensagem — ex: "Solicitar acesso"
  // quando error.body.error === "project_not_authorized" em
  // ProjectSelector.tsx. Genérico de propósito, reusável por qualquer
  // tela que precise de uma ação a mais além de só mostrar o erro.
  action?: { label: string; onClick: () => void }
  // false esconde error.body.fix mesmo quando presente — usado em
  // ProjectSelector.tsx: comandos gcloud de remediação de IAM (ex:
  // ProjectAccessDeniedError) são úteis pra quem administra o projeto
  // GCP alvo, não pro usuário comum só tentando acessar um projeto —
  // mostrar ali é ruído/confuso, não uma ação que ele consegue tomar.
  showFix?: boolean
}

// Mostra error.body.fix (comandos gcloud prontos, ex: LoggingAccessDeniedError)
// quando presente e showFix !== false — hoje só domains/lineage devolve
// isso de forma acionável; domains/access (item 7) reaproveita o mesmo
// shape de erro.
export function ApiErrorNotice({ error, action, showFix = true }: ApiErrorNoticeProps) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : 'Erro inesperado.'
  const fix = showFix && error instanceof ApiError ? error.body?.fix : undefined

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-status-error/30 bg-status-error/10 p-3 text-sm text-status-error">
      <div className="flex flex-wrap items-center gap-2">
        <CircleAlert size={16} className="shrink-0" />
        <span className="flex-1">{message}</span>
        {action && (
          <Button size="sm" variant="outline" onClick={action.onClick}>
            {action.label}
          </Button>
        )}
      </div>
      {fix && fix.length > 0 && (
        <pre className="overflow-x-auto rounded bg-background/50 p-2 font-mono text-xs text-foreground">
          {fix.join('\n')}
        </pre>
      )}
    </div>
  )
}
