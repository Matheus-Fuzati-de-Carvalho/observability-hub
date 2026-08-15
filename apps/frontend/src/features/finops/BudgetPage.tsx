import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useBudget } from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import type { CostlyQuery, DatasetCost, TopSpender } from '@/types/finops'

function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

type DatasetSortKey = 'dataset_id' | 'cost_usd'

function compareDataset(a: DatasetCost, b: DatasetCost, key: DatasetSortKey): number {
  if (key === 'cost_usd') return a.cost_usd - b.cost_usd
  return a.dataset_id.localeCompare(b.dataset_id)
}

type QuerySortKey = 'executed_at' | 'cost_usd' | 'billed_bytes'

function compareQuery(a: CostlyQuery, b: CostlyQuery, key: QuerySortKey): number {
  if (key === 'cost_usd') return a.cost_usd - b.cost_usd
  if (key === 'billed_bytes') return a.billed_bytes - b.billed_bytes
  return a.executed_at.localeCompare(b.executed_at)
}

type SpenderSortKey = 'principal_email' | 'cost_usd' | 'job_count'

function compareSpender(a: TopSpender, b: TopSpender, key: SpenderSortKey): number {
  if (key === 'cost_usd') return a.cost_usd - b.cost_usd
  if (key === 'job_count') return a.job_count - b.job_count
  return a.principal_email.localeCompare(b.principal_email)
}

export function BudgetPage() {
  const { projectId } = useProjectContext()
  const query = useBudget(projectId)
  const data = query.data

  const {
    sortKey: datasetSortKey,
    sortDir: datasetSortDir,
    toggleSort: toggleDatasetSort,
    visibleRows: visibleDatasets,
  } = useTableFilterSort<DatasetCost, DatasetSortKey>({
    rows: data?.by_dataset ?? [],
    initialSortKey: 'cost_usd',
    compare: compareDataset,
    matches: () => true,
  })

  const {
    sortKey: querySortKey,
    sortDir: querySortDir,
    toggleSort: toggleQuerySort,
    visibleRows: visibleQueries,
  } = useTableFilterSort<CostlyQuery, QuerySortKey>({
    rows: data?.top_queries ?? [],
    initialSortKey: 'cost_usd',
    compare: compareQuery,
    matches: () => true,
  })

  const {
    sortKey: spenderSortKey,
    sortDir: spenderSortDir,
    toggleSort: toggleSpenderSort,
    visibleRows: visibleSpenders,
  } = useTableFilterSort<TopSpender, SpenderSortKey>({
    rows: data?.top_spenders ?? [],
    initialSortKey: 'cost_usd',
    compare: compareSpender,
    matches: () => true,
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">FinOps — Budget de custo</h1>
          <p className="text-sm text-muted-foreground">
            Custo por dataset, queries mais caras e top gastadores do mês corrente — estimativa
            baseada em bytes escaneados, cobrança on-demand.
          </p>
        </div>
        <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
      </div>

      {query.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {query.isError && <ApiErrorNotice error={query.error} />}

      {data && (
        <>
          {data.warning && (
            <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
              {data.warning}
            </div>
          )}

          <div className="flex flex-wrap gap-4">
            {[
              { label: 'Custo até agora', value: formatUsd(data.projection.cost_so_far_usd) },
              { label: 'Média diária', value: formatUsd(data.projection.daily_average_usd) },
              {
                label: 'Projeção do mês',
                value: formatUsd(data.projection.projected_month_total_usd),
              },
              {
                label: 'Dias decorridos',
                value: `${data.projection.days_elapsed} de ${data.projection.days_in_month}`,
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

          <div className="flex flex-col gap-2">
            <p className="text-sm font-semibold">Custo por dataset</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead
                    label="Dataset"
                    active={datasetSortKey === 'dataset_id'}
                    direction={datasetSortDir}
                    onClick={() => toggleDatasetSort('dataset_id')}
                  />
                  <SortableTableHead
                    label="Custo"
                    active={datasetSortKey === 'cost_usd'}
                    direction={datasetSortDir}
                    onClick={() => toggleDatasetSort('cost_usd')}
                    align="right"
                  />
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleDatasets.map((d) => (
                  <TableRow key={d.dataset_id}>
                    <TableCell className="font-medium">{d.dataset_id}</TableCell>
                    <TableCell className="text-right">{formatUsd(d.cost_usd)}</TableCell>
                  </TableRow>
                ))}
                {visibleDatasets.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={2} className="text-center text-muted-foreground">
                      Nenhum custo registrado neste mês.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-sm font-semibold">Queries mais caras</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead
                    label="Executado em"
                    active={querySortKey === 'executed_at'}
                    direction={querySortDir}
                    onClick={() => toggleQuerySort('executed_at')}
                  />
                  <TableHead>Usuário</TableHead>
                  <TableHead>Tabelas</TableHead>
                  <TableHead>Query</TableHead>
                  <SortableTableHead
                    label="Bytes cobrados"
                    active={querySortKey === 'billed_bytes'}
                    direction={querySortDir}
                    onClick={() => toggleQuerySort('billed_bytes')}
                    align="right"
                  />
                  <SortableTableHead
                    label="Custo"
                    active={querySortKey === 'cost_usd'}
                    direction={querySortDir}
                    onClick={() => toggleQuerySort('cost_usd')}
                    align="right"
                  />
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleQueries.map((q) => (
                  <TableRow key={q.job_id}>
                    <TableCell className="text-muted-foreground">
                      {formatDate(q.executed_at)}
                    </TableCell>
                    <TableCell>{q.principal_email}</TableCell>
                    <TableCell>
                      <div className="flex max-w-[200px] flex-wrap gap-1">
                        {q.tables.map((t) => (
                          <Badge key={t} variant="outline" className="truncate" title={t}>
                            {t.split('.').slice(1).join('.')}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell
                      className="max-w-[240px] truncate font-mono text-xs text-muted-foreground"
                      title={q.query_text ?? undefined}
                    >
                      {q.query_text ? truncate(q.query_text, 60) : '—'}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {formatBytes(q.billed_bytes)}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatUsd(q.cost_usd)}
                    </TableCell>
                  </TableRow>
                ))}
                {visibleQueries.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      Nenhuma query com custo neste mês.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-sm font-semibold">Top gastadores</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead
                    label="Usuário"
                    active={spenderSortKey === 'principal_email'}
                    direction={spenderSortDir}
                    onClick={() => toggleSpenderSort('principal_email')}
                  />
                  <SortableTableHead
                    label="Jobs"
                    active={spenderSortKey === 'job_count'}
                    direction={spenderSortDir}
                    onClick={() => toggleSpenderSort('job_count')}
                    align="right"
                  />
                  <SortableTableHead
                    label="Custo"
                    active={spenderSortKey === 'cost_usd'}
                    direction={spenderSortDir}
                    onClick={() => toggleSpenderSort('cost_usd')}
                    align="right"
                  />
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleSpenders.map((s) => (
                  <TableRow key={s.principal_email}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{s.principal_email}</span>
                        <Badge variant={s.is_service_account ? 'outline' : 'default'}>
                          {s.is_service_account ? 'Service account' : 'Humano'}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {formatNumber(s.job_count)}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatUsd(s.cost_usd)}
                    </TableCell>
                  </TableRow>
                ))}
                {visibleSpenders.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground">
                      Nenhum gasto registrado neste mês.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
