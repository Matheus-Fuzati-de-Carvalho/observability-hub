import { useEffect, useState } from 'react'
import { SqlPreview } from '@/components/SqlPreview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AccessTab } from '@/features/access/AccessTab'
import { useTableDetail } from '@/features/catalog/hooks'
import { ColumnTypeSuggestionsTab } from '@/features/finops/ColumnTypeSuggestionsTab'
import { LineageTab } from '@/features/lineage/LineageTab'
import { PiiTab } from '@/features/pii/PiiTab'
import { ColumnResultsTable } from '@/features/quality/ColumnResultsTable'
import { HistoryTab } from '@/features/quality/HistoryTab'
import { useEstimateProfiling, useRunProfiling } from '@/features/quality/hooks'
import { SchemaTable } from '@/features/quality/SchemaTable'
import { formatNumber, formatPercent } from '@/lib/format'
import { ApiError } from '@/lib/http-client'
import type { UniquenessMethod } from '@/types/profiling'

const NO_DATE_COLUMN = '__none__'
const DATE_TYPES = new Set(['DATE', 'DATETIME', 'TIMESTAMP'])
const VIEW_TYPES = new Set(['VIEW', 'MATERIALIZED_VIEW'])
const SCHEMA_TAB = 'schema'
const ANALYSIS_TAB = 'analysis'
const HISTORY_TAB = 'history'
const LINEAGE_TAB = 'lineage'
const PII_TAB = 'pii'
const ACCESS_TAB = 'access'
const COLUMN_TYPES_TAB = 'column-types'

// SelectValue não deriva o rótulo a partir dos SelectItem filhos nesta
// versão do base-ui — precisa de um render-prop mapeando valor -> rótulo.
const UNIQUENESS_METHOD_LABELS: Record<UniquenessMethod, string> = {
  approx: 'Aproximado (HLL)',
  exact: 'Exato',
}

interface ProfilingDialogProps {
  projectId: string
  datasetId: string
  tableId: string | null
  onOpenChange: (open: boolean) => void
}

export function ProfilingDialog({
  projectId,
  datasetId,
  tableId,
  onOpenChange,
}: ProfilingDialogProps) {
  const [samplePercent, setSamplePercent] = useState(100)
  const [uniquenessMethod, setUniquenessMethod] = useState<UniquenessMethod>('approx')
  const [dateColumn, setDateColumn] = useState(NO_DATE_COLUMN)
  const [dateWindowDays, setDateWindowDays] = useState(30)
  const [activeTab, setActiveTab] = useState<string>(SCHEMA_TAB)

  const tableDetailQuery = useTableDetail(projectId, datasetId, tableId ?? undefined)
  const estimateMutation = useEstimateProfiling()
  const runMutation = useRunProfiling()

  // Reset ao trocar de tabela — mutations do TanStack Query não limpam
  // sozinhas quando o alvo muda. tableId é usado só como gatilho (o efeito
  // não lê o valor); estimateMutation/runMutation não entram nas deps
  // porque .reset é uma nova referência a cada render — incluí-las
  // reexecutaria o reset em loop. Volta pra aba Schema também — abre
  // sempre nela, mesmo se a tabela anterior tinha sido aberta na aba de
  // análise.
  // biome-ignore lint/correctness/useExhaustiveDependencies: ver comentário acima
  useEffect(() => {
    setSamplePercent(100)
    setUniquenessMethod('approx')
    setDateColumn(NO_DATE_COLUMN)
    setDateWindowDays(30)
    setActiveTab(SCHEMA_TAB)
    estimateMutation.reset()
    runMutation.reset()
  }, [tableId])

  const partitionColumn = tableDetailQuery.data?.partition_column ?? null
  const dateColumns =
    tableDetailQuery.data?.columns.filter((c) => DATE_TYPES.has(c.data_type.toUpperCase())) ?? []
  // Coluna de partição do tipo data aparece primeiro na lista, como opção
  // recomendada — geralmente é o melhor candidato pra filtro temporal.
  const orderedDateColumns =
    partitionColumn && dateColumns.some((c) => c.column_name === partitionColumn)
      ? [
          ...dateColumns.filter((c) => c.column_name === partitionColumn),
          ...dateColumns.filter((c) => c.column_name !== partitionColumn),
        ]
      : dateColumns
  const isView = Boolean(tableDetailQuery.data && VIEW_TYPES.has(tableDetailQuery.data.table_type))

  function buildRequest() {
    const hasDateFilter = dateColumn !== NO_DATE_COLUMN
    return {
      projectId,
      datasetId,
      tableId: tableId as string,
      sample_percent: samplePercent,
      uniqueness_method: uniquenessMethod,
      date_column: hasDateFilter ? dateColumn : null,
      date_window_days: hasDateFilter ? dateWindowDays : null,
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

  // sm:max-w-sm do DialogContent base vence w-[90vw]/max-w-[1000px] na
  // cascata em qualquer tela >=640px (aparece depois no CSS gerado,
  // independente da ordem no className) — precisa de ! pra sobrepor.
  //
  // flex-col + overflow-hidden no lugar de overflow-y-auto solto: com
  // overflow-y definido e overflow-x ausente, o CSS computa overflow-x
  // como "auto" também (regra do spec pra quando só um eixo é "visible")
  // — isso fazia qualquer tabela larga arrastar o header/controles fixos
  // pro scroll horizontal junto. Cada TabsContent tem seu próprio
  // overflow-y-auto isolado; scroll horizontal de cada tabela continua
  // isolado nela mesma (Table já tem overflow-x-auto em
  // components/ui/table.tsx). min-h-0 nos flex items intermediários é
  // necessário pra eles poderem encolher abaixo do tamanho do conteúdo —
  // sem isso o overflow-y-auto do filho nunca entra em ação.
  return (
    <Dialog open={Boolean(tableId)} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-[90vw]! max-w-[1000px]! flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <p className="text-xs font-semibold tracking-wide text-primary uppercase">
            Módulo de qualidade
          </p>
          <DialogTitle className="text-lg">
            {datasetId}.{tableId}
          </DialogTitle>
          <DialogDescription>
            Amostragem, unicidade e completude coluna a coluna, com estimativa de custo antes de
            executar.
          </DialogDescription>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as string)}
          className="flex min-h-0 flex-1 flex-col"
        >
          <TabsList className="w-fit shrink-0">
            <TabsTrigger value={SCHEMA_TAB}>Schema</TabsTrigger>
            <TabsTrigger value={ANALYSIS_TAB} className="gap-1.5">
              Análise de qualidade
              {runMutation.data && (
                <>
                  <span aria-hidden="true" className="size-1.5 rounded-full bg-status-ok" />
                  <span className="sr-only">Resultado de profile disponível</span>
                </>
              )}
            </TabsTrigger>
            <TabsTrigger value={HISTORY_TAB}>Histórico</TabsTrigger>
            <TabsTrigger value={LINEAGE_TAB}>Lineage</TabsTrigger>
            <TabsTrigger value={PII_TAB}>PII</TabsTrigger>
            <TabsTrigger value={ACCESS_TAB}>Acesso</TabsTrigger>
            <TabsTrigger value={COLUMN_TYPES_TAB}>Tipos de coluna</TabsTrigger>
          </TabsList>

          <TabsContent value={SCHEMA_TAB} className="flex min-h-0 flex-1 flex-col gap-3">
            {(tableDetailQuery.data?.is_partitioned || tableDetailQuery.data?.is_clustered) && (
              <div className="flex shrink-0 flex-wrap gap-2">
                {tableDetailQuery.data?.is_partitioned && (
                  <Badge>Particionada por {tableDetailQuery.data.partition_column}</Badge>
                )}
                {tableDetailQuery.data?.is_clustered && (
                  <Badge variant="outline">
                    Clusterizada por {tableDetailQuery.data.clustering_columns.join(', ')}
                  </Badge>
                )}
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-y-auto">
              <SchemaTable
                columns={tableDetailQuery.data?.columns ?? []}
                isLoading={tableDetailQuery.isLoading}
                partitionColumn={partitionColumn}
              />
            </div>
          </TabsContent>

          <TabsContent value={ANALYSIS_TAB} className="flex min-h-0 flex-1 flex-col gap-4">
            <div className="flex shrink-0 flex-wrap items-end gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="sample-percent">Amostragem (%)</Label>
                <Input
                  id="sample-percent"
                  type="number"
                  min={1}
                  max={100}
                  className="w-24"
                  value={samplePercent}
                  onChange={(e) => setSamplePercent(Number(e.target.value))}
                  disabled={isView}
                />
                {isView && (
                  <p className="text-xs text-status-warn">Amostragem não disponível para views</p>
                )}
              </div>

              <div className="flex flex-col gap-1.5">
                <Label>Método unicidade</Label>
                <Select
                  value={uniquenessMethod}
                  onValueChange={(value) => setUniquenessMethod(value as UniquenessMethod)}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue>
                      {(value: UniquenessMethod) => UNIQUENESS_METHOD_LABELS[value]}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="approx">Aproximado (HLL)</SelectItem>
                    <SelectItem value="exact">Exato</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label>Coluna de data</Label>
                <Select
                  value={dateColumn}
                  onValueChange={(value) => setDateColumn(value ?? NO_DATE_COLUMN)}
                >
                  <SelectTrigger className="w-40">
                    <SelectValue>
                      {(value: string) => (value === NO_DATE_COLUMN ? 'Nenhuma' : value)}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_DATE_COLUMN}>Nenhuma</SelectItem>
                    {orderedDateColumns.map((column) => (
                      <SelectItem key={column.column_name} value={column.column_name}>
                        {column.column_name}
                        {column.column_name === partitionColumn ? ' (recomendada)' : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {dateColumn !== NO_DATE_COLUMN && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="date-window">Janela (dias)</Label>
                  <Input
                    id="date-window"
                    type="number"
                    min={1}
                    className="w-24"
                    value={dateWindowDays}
                    onChange={(e) => setDateWindowDays(Number(e.target.value))}
                  />
                </div>
              )}

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
                  {runMutation.isPending ? 'Executando…' : 'Executar profile'}
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
                    <Separator />
                    <div className="flex flex-wrap gap-4">
                      {[
                        {
                          label: 'Amostradas',
                          value: formatNumber(runMutation.data.table_summary.total_sampled_rows),
                        },
                        {
                          label: 'Total da tabela',
                          value: formatNumber(runMutation.data.table_summary.total_table_rows),
                        },
                        {
                          label: 'Duplicatas est.',
                          value: formatPercent(
                            runMutation.data.table_summary.estimated_duplicate_pct,
                          ),
                        },
                        {
                          label: 'Densidade geral',
                          value: formatPercent(runMutation.data.table_summary.overall_density),
                        },
                      ].map((item) => (
                        <div
                          key={item.label}
                          className="min-w-[160px] flex-1 rounded-lg border border-border bg-card p-4"
                        >
                          <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                            {item.label}
                          </p>
                          <p className="text-2xl font-bold">{item.value}</p>
                        </div>
                      ))}
                    </div>

                    {runMutation.data.excluded_columns.length > 0 && (
                      <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        Colunas excluídas do profiling:
                        {runMutation.data.excluded_columns.map((excluded) => (
                          <Badge
                            key={excluded.column_name}
                            variant="outline"
                            title={excluded.reason}
                          >
                            {excluded.column_name}
                          </Badge>
                        ))}
                      </p>
                    )}

                    <ColumnResultsTable columns={runMutation.data.columns} />
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
          </TabsContent>

          <TabsContent value={HISTORY_TAB} className="min-h-0 flex-1 overflow-y-auto">
            <HistoryTab projectId={projectId} datasetId={datasetId} tableId={tableId} />
          </TabsContent>

          <TabsContent value={LINEAGE_TAB} className="min-h-0 flex-1 overflow-y-auto">
            <LineageTab projectId={projectId} datasetId={datasetId} tableId={tableId} />
          </TabsContent>

          <TabsContent value={PII_TAB} className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <PiiTab projectId={projectId} datasetId={datasetId} tableId={tableId} isView={isView} />
          </TabsContent>

          <TabsContent value={ACCESS_TAB} className="min-h-0 flex-1 overflow-y-auto">
            <AccessTab projectId={projectId} datasetId={datasetId} tableId={tableId} />
          </TabsContent>

          <TabsContent
            value={COLUMN_TYPES_TAB}
            className="flex min-h-0 flex-1 flex-col overflow-hidden"
          >
            <ColumnTypeSuggestionsTab
              projectId={projectId}
              datasetId={datasetId}
              tableId={tableId}
              isView={isView}
            />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
