import { CheckCircle2, Loader2, Search as SearchIcon, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useSearchTables } from '@/features/catalog/hooks'
import { SearchAbsentTable } from '@/features/catalog/SearchAbsentTable'
import { SearchMatchesTable } from '@/features/catalog/SearchMatchesTable'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { ApiError } from '@/lib/http-client'
import type { SearchMode } from '@/types/catalog'

export function SearchPage() {
  const { projectId } = useProjectContext()
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<SearchMode>('exact')
  const searchMutation = useSearchTables()

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!projectId || !q.trim()) return
    searchMutation.mutate({ projectId, q: q.trim(), mode })
  }

  const errorMessage =
    searchMutation.error instanceof ApiError
      ? searchMutation.error.message
      : searchMutation.error instanceof Error
        ? searchMutation.error.message
        : null

  const result = searchMutation.data
  const hasNoResults = Boolean(
    result && result.datasets_with_match.length === 0 && result.datasets_without_match.length === 0,
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Busca</h1>
        <p className="text-sm text-muted-foreground">
          Encontre em quais datasets uma tabela existe (ou não) dentro do projeto selecionado.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-[240px] flex-1 flex-col gap-1.5">
          <Label htmlFor="search-q">Nome da tabela ou partição</Label>
          <Input
            id="search-q"
            placeholder="ex: events_20260812, ga4_events, crm"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        <div className="flex gap-1 rounded-md border border-border p-1">
          <Button
            type="button"
            size="sm"
            variant={mode === 'exact' ? 'default' : 'ghost'}
            onClick={() => setMode('exact')}
          >
            Exato
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === 'contains' ? 'default' : 'ghost'}
            onClick={() => setMode('contains')}
          >
            Contém
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === 'not_contains' ? 'default' : 'ghost'}
            onClick={() => setMode('not_contains')}
          >
            Não contém
          </Button>
        </div>

        <Button type="submit" disabled={!q.trim() || searchMutation.isPending}>
          <SearchIcon size={14} />
          Buscar
        </Button>
      </form>

      {searchMutation.isPending && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Essa consulta pode demorar alguns segundos dependendo do tamanho do projeto…
        </div>
      )}

      {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}

      {result && hasNoResults && (
        <p className="text-sm text-muted-foreground">
          Nenhuma tabela encontrada com esse termo no projeto {result.project_id}.
        </p>
      )}

      {result && !hasNoResults && (
        <div className="flex flex-col gap-6">
          {result.datasets_with_match.length > 0 && (
            <div>
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <CheckCircle2 size={16} className="text-status-ok" />
                Encontrado em {result.datasets_with_match.length}{' '}
                {result.datasets_with_match.length === 1 ? 'dataset' : 'datasets'}
              </h2>
              <SearchMatchesTable matches={result.datasets_with_match} />
            </div>
          )}

          {result.datasets_without_match.length > 0 && (
            <div>
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <XCircle size={16} className="text-status-error" />
                Ausente em {result.datasets_without_match.length}{' '}
                {result.datasets_without_match.length === 1 ? 'dataset' : 'datasets'}
              </h2>
              <SearchAbsentTable datasets={result.datasets_without_match} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
