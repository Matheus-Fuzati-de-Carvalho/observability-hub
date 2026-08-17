import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ColumnTypeScopePicker } from '@/features/finops/ColumnTypeScopePicker'
import { ColumnTypeSuggestionBadges } from '@/features/finops/ColumnTypeSuggestionBadges'
import {
  useEstimateColumnTypeSuggestions,
  usePartitionCandidates,
  useRunColumnTypeSuggestions,
  useUnusedTables,
} from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import { ApiError } from '@/lib/http-client'
import type {
  ColumnTypeCandidate,
  MinDaysUnused,
  PartitionCandidate,
  UnusedTable,
} from '@/types/finops'

const UNUSED_TAB = 'unused'
const PARTITION_TAB = 'partition'
const COLUMN_TYPES_TAB = 'column-types'
const MIN_DAYS_OPTIONS: MinDaysUnused[] = [30, 60, 90]
const DATASET_FILTER_ALL = 'all'
const ESTIMATE_FILTER_ALL = 'all'
const ESTIMATE_FILTER_WITH = 'with'
const ESTIMATE_FILTER_WITHOUT = 'without'
type EstimateFilter =
  | typeof ESTIMATE_FILTER_ALL
  | typeof ESTIMATE_FILTER_WITH
  | typeof ESTIMATE_FILTER_WITHOUT

function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

function matchesSearch(datasetId: string, tableId: string, term: string): boolean {
  const needle = term.toLowerCase()
  return tableId.toLowerCase().includes(needle) || datasetId.toLowerCase().includes(needle)
}

export function FinOpsPage() {
  const { projectId } = useProjectContext()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">FinOps — Scanner de desperdício</h1>
        <p className="text-sm text-muted-foreground">
          Tabelas sem uso, candidatas a particionamento e sugestões de tipo de coluna, com
          estimativa de custo.
        </p>
      </div>

      <Tabs defaultValue={UNUSED_TAB}>
        <TabsList className="w-fit">
          <TabsTrigger value={UNUSED_TAB}>Tabelas sem uso</TabsTrigger>
          <TabsTrigger value={PARTITION_TAB}>Candidatas a particionamento</TabsTrigger>
          <TabsTrigger value={COLUMN_TYPES_TAB}>Tipos de coluna</TabsTrigger>
        </TabsList>

        <TabsContent value={UNUSED_TAB}>
          <UnusedTablesTab projectId={projectId} />
        </TabsContent>

        <TabsContent value={PARTITION_TAB}>
          <PartitionCandidatesTab projectId={projectId} />
        </TabsContent>

        <TabsContent value={COLUMN_TYPES_TAB}>
          <ColumnTypesTab projectId={projectId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

type UnusedSortKey =
  | 'table_id'
  | 'size_bytes'
  | 'last_accessed_at'
  | 'estimated_monthly_storage_cost_usd'

function compareUnused(a: UnusedTable, b: UnusedTable, key: UnusedSortKey): number {
  if (key === 'size_bytes') return a.size_bytes - b.size_bytes
  if (key === 'estimated_monthly_storage_cost_usd') {
    return a.estimated_monthly_storage_cost_usd - b.estimated_monthly_storage_cost_usd
  }
  if (key === 'last_accessed_at') {
    return (a.last_accessed_at ?? '').localeCompare(b.last_accessed_at ?? '')
  }
  return a.table_id.localeCompare(b.table_id)
}

function UnusedTablesTab({ projectId }: { projectId: string | undefined }) {
  const [minDaysUnused, setMinDaysUnused] = useState<MinDaysUnused>(30)
  const query = useUnusedTables(projectId, minDaysUnused)
  const data = query.data

  const datasets = useMemo(
    () => [...new Set(data?.tables.map((t) => t.dataset_id) ?? [])].sort(),
    [data],
  )
  const [datasetFilter, setDatasetFilter] = useState(DATASET_FILTER_ALL)

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleTables,
  } = useTableFilterSort<UnusedTable, UnusedSortKey>({
    rows: data?.tables ?? [],
    initialSortKey: 'size_bytes',
    compare: compareUnused,
    matches: (table, term) =>
      matchesSearch(table.dataset_id, table.table_id, term) &&
      (datasetFilter === DATASET_FILTER_ALL || table.dataset_id === datasetFilter),
  })

  if (query.isLoading) {
    return <p className="mt-4 text-sm text-muted-foreground">Carregando…</p>
  }

  if (query.isError) {
    return (
      <div className="mt-4">
        <ApiErrorNotice error={query.error} />
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por nome da tabela…"
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Sem uso há pelo menos</span>
          <Select
            value={String(minDaysUnused)}
            onValueChange={(value) => setMinDaysUnused(Number(value) as MinDaysUnused)}
          >
            <SelectTrigger className="w-24">
              <SelectValue>{(value: string) => `${value} dias`}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {MIN_DAYS_OPTIONS.map((days) => (
                <SelectItem key={days} value={String(days)}>
                  {days} dias
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Select
          value={datasetFilter}
          onValueChange={(value) => setDatasetFilter(value ?? DATASET_FILTER_ALL)}
        >
          <SelectTrigger className="w-52">
            <SelectValue>
              {(value: string) => (value === DATASET_FILTER_ALL ? 'Todos os datasets' : value)}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={DATASET_FILTER_ALL}>Todos os datasets</SelectItem>
            {datasets.map((dataset) => (
              <SelectItem key={dataset} value={dataset}>
                {dataset}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          {visibleTables.length} de {data.tables.length} tabela{data.tables.length === 1 ? '' : 's'}
        </span>
        <div className="ml-auto">
          <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
        </div>
      </div>

      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Tabela"
              active={sortKey === 'table_id'}
              direction={sortDir}
              onClick={() => toggleSort('table_id')}
            />
            <SortableTableHead
              label="Tamanho"
              active={sortKey === 'size_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('size_bytes')}
              align="right"
            />
            <SortableTableHead
              label="Último acesso"
              active={sortKey === 'last_accessed_at'}
              direction={sortDir}
              onClick={() => toggleSort('last_accessed_at')}
            />
            <SortableTableHead
              label="Custo de storage estimado/mês"
              active={sortKey === 'estimated_monthly_storage_cost_usd'}
              direction={sortDir}
              onClick={() => toggleSort('estimated_monthly_storage_cost_usd')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleTables.map((table) => (
            <TableRow key={`${data.project_id}.${table.dataset_id}.${table.table_id}`}>
              <TableCell>
                <Link to={`/datasets/${table.dataset_id}`} className="hover:text-primary">
                  {data.project_id}.{table.dataset_id}
                </Link>
                .{table.table_id}
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {formatBytes(table.size_bytes)}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {table.last_accessed_at
                  ? formatDate(table.last_accessed_at)
                  : `Nunca nos últimos ${data.lookback_days} dias`}
              </TableCell>
              <TableCell className="text-right font-medium">
                {formatUsd(table.estimated_monthly_storage_cost_usd)}
              </TableCell>
            </TableRow>
          ))}
          {visibleTables.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                {data.tables.length === 0
                  ? 'Nenhuma tabela sem uso encontrada.'
                  : 'Nenhuma tabela encontrada com esse filtro.'}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

type PartitionSortKey =
  | 'table_id'
  | 'size_bytes'
  | 'observed_cost_usd_30d'
  | 'estimated_savings_usd_conservative'

function comparePartition(
  a: PartitionCandidate,
  b: PartitionCandidate,
  key: PartitionSortKey,
): number {
  if (key === 'size_bytes') return a.size_bytes - b.size_bytes
  if (key === 'observed_cost_usd_30d') return a.observed_cost_usd_30d - b.observed_cost_usd_30d
  if (key === 'estimated_savings_usd_conservative') {
    return (
      (a.estimated_savings_usd_conservative ?? -1) - (b.estimated_savings_usd_conservative ?? -1)
    )
  }
  return a.table_id.localeCompare(b.table_id)
}

function PartitionCandidatesTab({ projectId }: { projectId: string | undefined }) {
  const query = usePartitionCandidates(projectId)
  const data = query.data
  const [estimateFilter, setEstimateFilter] = useState<EstimateFilter>(ESTIMATE_FILTER_ALL)

  const datasets = useMemo(
    () => [...new Set(data?.candidates.map((c) => c.dataset_id) ?? [])].sort(),
    [data],
  )
  const [datasetFilter, setDatasetFilter] = useState(DATASET_FILTER_ALL)

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleCandidates,
  } = useTableFilterSort<PartitionCandidate, PartitionSortKey>({
    rows: data?.candidates ?? [],
    initialSortKey: 'observed_cost_usd_30d',
    compare: comparePartition,
    matches: (candidate, term) => {
      const hasEstimate = candidate.estimated_savings_usd_conservative !== null
      const matchesEstimate =
        estimateFilter === ESTIMATE_FILTER_ALL ||
        (estimateFilter === ESTIMATE_FILTER_WITH && hasEstimate) ||
        (estimateFilter === ESTIMATE_FILTER_WITHOUT && !hasEstimate)
      const matchesDataset =
        datasetFilter === DATASET_FILTER_ALL || candidate.dataset_id === datasetFilter
      return (
        matchesSearch(candidate.dataset_id, candidate.table_id, term) &&
        matchesEstimate &&
        matchesDataset
      )
    },
  })

  if (query.isLoading) {
    return <p className="mt-4 text-sm text-muted-foreground">Carregando…</p>
  }

  if (query.isError) {
    return (
      <div className="mt-4">
        <ApiErrorNotice error={query.error} />
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por nome da tabela…"
            className="pl-8"
          />
        </div>
        <Select
          value={estimateFilter}
          onValueChange={(value) =>
            setEstimateFilter((value as EstimateFilter) ?? ESTIMATE_FILTER_ALL)
          }
        >
          <SelectTrigger className="w-52">
            <SelectValue>
              {(value: EstimateFilter) =>
                value === ESTIMATE_FILTER_WITH
                  ? 'Com estimativa de economia'
                  : value === ESTIMATE_FILTER_WITHOUT
                    ? 'Sem estimativa de economia'
                    : 'Todas'
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ESTIMATE_FILTER_ALL}>Todas</SelectItem>
            <SelectItem value={ESTIMATE_FILTER_WITH}>Com estimativa de economia</SelectItem>
            <SelectItem value={ESTIMATE_FILTER_WITHOUT}>Sem estimativa de economia</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={datasetFilter}
          onValueChange={(value) => setDatasetFilter(value ?? DATASET_FILTER_ALL)}
        >
          <SelectTrigger className="w-52">
            <SelectValue>
              {(value: string) => (value === DATASET_FILTER_ALL ? 'Todos os datasets' : value)}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={DATASET_FILTER_ALL}>Todos os datasets</SelectItem>
            {datasets.map((dataset) => (
              <SelectItem key={dataset} value={dataset}>
                {dataset}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          {visibleCandidates.length} de {data.candidates.length} candidata
          {data.candidates.length === 1 ? '' : 's'} — custo observado nos últimos{' '}
          {data.lookback_days} dias
        </span>
        <div className="ml-auto">
          <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
        </div>
      </div>

      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Tabela"
              active={sortKey === 'table_id'}
              direction={sortDir}
              onClick={() => toggleSort('table_id')}
            />
            <SortableTableHead
              label="Tamanho"
              active={sortKey === 'size_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('size_bytes')}
              align="right"
            />
            <TableHead>Coluna candidata</TableHead>
            <SortableTableHead
              label="Custo observado (30d)"
              active={sortKey === 'observed_cost_usd_30d'}
              direction={sortDir}
              onClick={() => toggleSort('observed_cost_usd_30d')}
              align="right"
            />
            <SortableTableHead
              label="Economia estimada"
              active={sortKey === 'estimated_savings_usd_conservative'}
              direction={sortDir}
              onClick={() => toggleSort('estimated_savings_usd_conservative')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleCandidates.map((candidate) => (
            <TableRow key={`${data.project_id}.${candidate.dataset_id}.${candidate.table_id}`}>
              <TableCell>
                <Link to={`/datasets/${candidate.dataset_id}`} className="hover:text-primary">
                  {data.project_id}.{candidate.dataset_id}
                </Link>
                .{candidate.table_id}
                <span className="ml-2 text-xs text-muted-foreground">
                  {formatNumber(candidate.row_count)} linhas
                </span>
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {formatBytes(candidate.size_bytes)}
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {candidate.candidate_partition_columns.map((col) => (
                    <Badge key={col} variant="outline">
                      {col}
                    </Badge>
                  ))}
                </div>
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {formatUsd(candidate.observed_cost_usd_30d)}
              </TableCell>
              <TableCell className="text-right">
                {candidate.estimated_savings_usd_conservative !== null &&
                candidate.estimated_savings_usd_optimistic !== null ? (
                  <span
                    className="font-medium text-status-ok"
                    title={candidate.savings_disclaimer ?? undefined}
                  >
                    {formatUsd(candidate.estimated_savings_usd_conservative)} –{' '}
                    {formatUsd(candidate.estimated_savings_usd_optimistic)}
                  </span>
                ) : (
                  <span className="text-muted-foreground">Sem dado suficiente</span>
                )}
              </TableCell>
            </TableRow>
          ))}
          {visibleCandidates.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                {data.candidates.length === 0
                  ? 'Nenhuma candidata a particionamento encontrada.'
                  : 'Nenhuma candidata encontrada com esse filtro.'}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

type ColumnTypeSortKey = 'table_id' | 'size_bytes' | 'total_savings_usd_month'

function totalSavings(candidate: ColumnTypeCandidate): number {
  return candidate.suggestions.reduce((sum, s) => sum + s.estimated_storage_savings_usd_month, 0)
}

function compareColumnType(
  a: ColumnTypeCandidate,
  b: ColumnTypeCandidate,
  key: ColumnTypeSortKey,
): number {
  if (key === 'size_bytes') return a.size_bytes - b.size_bytes
  if (key === 'total_savings_usd_month') return totalSavings(a) - totalSavings(b)
  return a.table_id.localeCompare(b.table_id)
}

function ColumnTypesTab({ projectId }: { projectId: string | undefined }) {
  const [samplePercent, setSamplePercent] = useState(10)
  const [selectedScope, setSelectedScope] = useState<Set<string>>(new Set())
  const estimateMutation = useEstimateColumnTypeSuggestions()
  const runMutation = useRunColumnTypeSuggestions()
  const scopeTables = Array.from(selectedScope)
  const canRun = Boolean(projectId) && scopeTables.length > 0

  const activeError = estimateMutation.error ?? runMutation.error
  const errorMessage =
    activeError instanceof ApiError
      ? activeError.message
      : activeError instanceof Error
        ? activeError.message
        : null

  const candidates = runMutation.data?.candidates ?? []

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleCandidates,
  } = useTableFilterSort<ColumnTypeCandidate, ColumnTypeSortKey>({
    rows: candidates,
    initialSortKey: 'total_savings_usd_month',
    compare: compareColumnType,
    matches: (candidate, term) => matchesSearch(candidate.dataset_id, candidate.table_id, term),
  })

  return (
    <div className="mt-4 flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        Diferente das outras abas, este scan amostra dado real via <code>TABLESAMPLE</code> e tem
        custo real de BigQuery — escolha o escopo, estime antes de escanear.
      </p>

      <div className="flex flex-col gap-1.5">
        <Label>Escopo (datasets/tabelas)</Label>
        <ColumnTypeScopePicker
          projectId={projectId}
          selected={selectedScope}
          onChange={setSelectedScope}
        />
        <span className="text-xs text-muted-foreground">
          {scopeTables.length === 0
            ? 'Selecione ao menos uma tabela para habilitar o scan.'
            : `${scopeTables.length} tabela${scopeTables.length === 1 ? '' : 's'} selecionada${scopeTables.length === 1 ? '' : 's'}.`}
        </span>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="column-type-sample-percent">Amostragem (%)</Label>
          <Input
            id="column-type-sample-percent"
            type="number"
            min={1}
            max={100}
            className="w-24"
            value={samplePercent}
            onChange={(e) => setSamplePercent(Number(e.target.value))}
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={estimateMutation.isPending || !canRun}
            onClick={() =>
              projectId &&
              estimateMutation.mutate({ projectId, samplePercent, tables: scopeTables })
            }
          >
            {estimateMutation.isPending ? 'Estimando…' : 'Estimar custo'}
          </Button>
          <Button
            disabled={runMutation.isPending || !canRun}
            onClick={() =>
              projectId && runMutation.mutate({ projectId, samplePercent, tables: scopeTables })
            }
          >
            {runMutation.isPending ? 'Escaneando…' : 'Escanear'}
          </Button>
        </div>
      </div>

      {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}

      {estimateMutation.data && !runMutation.data && (
        <div className="flex flex-wrap gap-6 rounded-lg border border-border bg-card p-4 text-sm">
          <div>
            <p className="text-xs text-muted-foreground uppercase">Tabelas elegíveis</p>
            <p className="text-lg font-bold">{estimateMutation.data.tables_scanned}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase">Views puladas</p>
            <p className="text-lg font-bold">{estimateMutation.data.tables_skipped_view}</p>
          </div>
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

      {runMutation.data && (
        <>
          {runMutation.data.warning && (
            <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
              {runMutation.data.warning}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-[220px] flex-1">
              <Search
                size={14}
                className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
              />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filtrar por nome da tabela…"
                className="pl-8"
              />
            </div>
            <span className="text-sm text-muted-foreground">
              {visibleCandidates.length} de {candidates.length} tabela
              {candidates.length === 1 ? '' : 's'} com sugestão — {runMutation.data.tables_scanned}{' '}
              escaneadas, {runMutation.data.tables_skipped_view} views puladas
            </span>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <SortableTableHead
                  label="Tabela"
                  active={sortKey === 'table_id'}
                  direction={sortDir}
                  onClick={() => toggleSort('table_id')}
                />
                <SortableTableHead
                  label="Tamanho"
                  active={sortKey === 'size_bytes'}
                  direction={sortDir}
                  onClick={() => toggleSort('size_bytes')}
                  align="right"
                />
                <TableHead>Sugestões</TableHead>
                <SortableTableHead
                  label="Economia estimada/mês"
                  active={sortKey === 'total_savings_usd_month'}
                  direction={sortDir}
                  onClick={() => toggleSort('total_savings_usd_month')}
                  align="right"
                />
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleCandidates.map((candidate) => (
                <TableRow key={`${projectId}.${candidate.dataset_id}.${candidate.table_id}`}>
                  <TableCell>
                    <Link to={`/datasets/${candidate.dataset_id}`} className="hover:text-primary">
                      {projectId}.{candidate.dataset_id}
                    </Link>
                    .{candidate.table_id}
                    {candidate.row_count !== null && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        {formatNumber(candidate.row_count)} linhas
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatBytes(candidate.size_bytes)}
                  </TableCell>
                  <TableCell>
                    <ColumnTypeSuggestionBadges suggestions={candidate.suggestions} />
                  </TableCell>
                  <TableCell className="text-right font-medium text-status-ok">
                    {formatUsd(totalSavings(candidate))}
                  </TableCell>
                </TableRow>
              ))}
              {visibleCandidates.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    {candidates.length === 0
                      ? 'Nenhuma sugestão de tipo de coluna encontrada.'
                      : 'Nenhuma tabela encontrada com esse filtro.'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  )
}
