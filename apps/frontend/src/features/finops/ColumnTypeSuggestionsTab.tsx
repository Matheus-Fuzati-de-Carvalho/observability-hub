import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useEstimateColumnTypeSuggestions,
  useRunColumnTypeSuggestions,
} from '@/features/finops/hooks'
import { formatNumber } from '@/lib/format'
import { ApiError } from '@/lib/http-client'

interface ColumnTypeSuggestionsTabProps {
  projectId: string
  datasetId: string
  tableId: string | null
  isView: boolean
}

// Escopo implícito de uma tabela só (a aberta no modal) — diferente da
// aba de projeto em /finops, que precisa do ColumnTypeScopePicker
// porque roda em muitas tabelas de uma vez. Aqui o "escopo" é sempre
// `["{datasetId}.{tableId}"]`, mesmo endpoint e mesmo fluxo
// estimar->escanear, mirror de features/pii/PiiTab.tsx.
export function ColumnTypeSuggestionsTab({
  projectId,
  datasetId,
  tableId,
  isView,
}: ColumnTypeSuggestionsTabProps) {
  const [samplePercent, setSamplePercent] = useState(10)

  const estimateMutation = useEstimateColumnTypeSuggestions()
  const runMutation = useRunColumnTypeSuggestions()

  // Mesmo motivo do reset em PiiTab.tsx/ProfilingDialog.tsx: mutations do
  // TanStack Query não limpam sozinhas quando a tabela muda, e .reset é
  // uma nova referência a cada render — incluí-las nas deps reexecutaria
  // o reset em loop.
  // biome-ignore lint/correctness/useExhaustiveDependencies: ver comentário acima
  useEffect(() => {
    setSamplePercent(10)
    estimateMutation.reset()
    runMutation.reset()
  }, [tableId])

  if (!tableId) return null

  const tables = [`${datasetId}.${tableId}`]

  const activeError = estimateMutation.error ?? runMutation.error
  const errorMessage =
    activeError instanceof ApiError
      ? activeError.message
      : activeError instanceof Error
        ? activeError.message
        : null

  const candidate = runMutation.data?.candidates[0]

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="flex shrink-0 flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="column-type-tab-sample-percent">Amostragem (%)</Label>
          <Input
            id="column-type-tab-sample-percent"
            type="number"
            min={1}
            max={100}
            className="w-24"
            value={samplePercent}
            onChange={(e) => setSamplePercent(Number(e.target.value))}
            disabled={isView}
          />
          {isView && (
            <p className="text-xs text-status-warn">
              Amostragem não disponível para views — TABLESAMPLE não é suportado
            </p>
          )}
        </div>

        <div className="ml-auto flex gap-2">
          <Button
            variant="outline"
            disabled={estimateMutation.isPending || isView}
            onClick={() => estimateMutation.mutate({ projectId, samplePercent, tables })}
          >
            {estimateMutation.isPending ? 'Estimando…' : 'Estimar custo'}
          </Button>
          <Button
            disabled={runMutation.isPending || isView}
            onClick={() => runMutation.mutate({ projectId, samplePercent, tables })}
          >
            {runMutation.isPending ? 'Escaneando…' : 'Escanear'}
          </Button>
        </div>
      </div>

      {errorMessage && <p className="shrink-0 text-sm text-status-error">{errorMessage}</p>}

      {estimateMutation.data && !runMutation.data && (
        <div className="flex shrink-0 gap-6 rounded-lg border border-border bg-card p-4 text-sm">
          <div>
            <p className="text-xs text-muted-foreground uppercase">Bytes estimados</p>
            <p className="text-lg font-bold">{estimateMutation.data.estimated_bytes_human}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase">Custo estimado</p>
            <p className="text-lg font-bold">
              US$ {estimateMutation.data.estimated_cost_usd.toFixed(8)}
            </p>
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex flex-col gap-4">
          {runMutation.data && (
            <>
              {runMutation.data.warning && (
                <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
                  {runMutation.data.warning}
                </div>
              )}

              {candidate && candidate.suggestions.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Coluna</TableHead>
                      <TableHead>Tipo sugerido</TableHead>
                      <TableHead className="text-right">Amostrados</TableHead>
                      <TableHead className="text-right">Bytes (atual → sugerido)</TableHead>
                      <TableHead className="text-right">Economia estimada/mês</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {candidate.suggestions.map((s) => (
                      <TableRow key={s.column_name}>
                        <TableCell className="font-medium">{s.column_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{s.suggested_type}</Badge>
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatNumber(s.sample_non_null_count)}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {s.avg_current_bytes.toFixed(1)}B → {s.suggested_type_bytes}B
                        </TableCell>
                        <TableCell className="text-right font-medium text-status-ok">
                          US$ {s.estimated_storage_savings_usd_month.toFixed(6)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Nenhuma sugestão de tipo de coluna para esta tabela.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
