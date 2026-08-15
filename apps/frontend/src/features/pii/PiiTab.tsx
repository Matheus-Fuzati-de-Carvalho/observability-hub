import { useEffect, useState } from 'react'
import { SqlPreview } from '@/components/SqlPreview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useEstimatePiiScan, useRunPiiScan } from '@/features/pii/hooks'
import { PiiResultsTable } from '@/features/pii/PiiResultsTable'
import { ApiError } from '@/lib/http-client'

interface PiiTabProps {
  projectId: string
  datasetId: string
  tableId: string | null
  isView: boolean
}

export function PiiTab({ projectId, datasetId, tableId, isView }: PiiTabProps) {
  const [samplePercent, setSamplePercent] = useState(10)
  const [matchThresholdPct, setMatchThresholdPct] = useState(5)

  const estimateMutation = useEstimatePiiScan()
  const runMutation = useRunPiiScan()

  // Mesmo motivo do reset em ProfilingDialog.tsx: mutations do TanStack
  // Query não limpam sozinhas quando a tabela muda, e .reset é uma nova
  // referência a cada render — incluí-las nas deps reexecutaria o reset
  // em loop.
  // biome-ignore lint/correctness/useExhaustiveDependencies: ver comentário acima
  useEffect(() => {
    setSamplePercent(10)
    setMatchThresholdPct(5)
    estimateMutation.reset()
    runMutation.reset()
  }, [tableId])

  if (!tableId) return null

  function buildRequest() {
    return {
      projectId,
      datasetId,
      tableId: tableId as string,
      sample_percent: samplePercent,
      match_threshold_pct: matchThresholdPct,
    }
  }

  const activeError = estimateMutation.error ?? runMutation.error
  const errorMessage =
    activeError instanceof ApiError
      ? activeError.message
      : activeError instanceof Error
        ? activeError.message
        : null

  const sql = runMutation.data?.sql ?? estimateMutation.data?.sql

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div className="flex shrink-0 flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pii-sample-percent">Amostragem (%)</Label>
          <Input
            id="pii-sample-percent"
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
              Amostragem não disponível para views — só a heurística de nome roda
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pii-match-threshold">Limiar de sinalização (%)</Label>
          <Input
            id="pii-match-threshold"
            type="number"
            min={0}
            max={100}
            className="w-24"
            value={matchThresholdPct}
            onChange={(e) => setMatchThresholdPct(Number(e.target.value))}
            disabled={isView}
          />
        </div>

        <div className="ml-auto flex gap-2">
          <Button
            variant="outline"
            disabled={estimateMutation.isPending}
            onClick={() => estimateMutation.mutate(buildRequest())}
          >
            {estimateMutation.isPending ? 'Estimando…' : 'Estimar custo'}
          </Button>
          <Button
            disabled={runMutation.isPending}
            onClick={() => runMutation.mutate(buildRequest())}
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

              {runMutation.data.excluded_columns.length > 0 && (
                <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  Colunas excluídas do scan:
                  {runMutation.data.excluded_columns.map((excluded) => (
                    <Badge key={excluded.column_name} variant="outline" title={excluded.reason}>
                      {excluded.column_name}
                    </Badge>
                  ))}
                </p>
              )}

              <PiiResultsTable columns={runMutation.data.columns} />
            </>
          )}

          {sql && (
            <SqlPreview
              key={runMutation.data ? 'run' : 'estimate'}
              sql={sql}
              defaultOpen={!runMutation.data}
            />
          )}
        </div>
      </div>
    </div>
  )
}
