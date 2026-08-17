import { ChevronDown, ChevronUp } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { SqlPreview } from '@/components/SqlPreview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useBudget } from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { BudgetGroupBy, CostGroup, CostlyQuery } from '@/types/finops'

const COST_TAB = 'cost'
const QUERIES_TAB = 'queries'

const GROUP_BY_OPTIONS: { value: BudgetGroupBy; label: string }[] = [
  { value: 'table', label: 'Tabela' },
  { value: 'user', label: 'Usuário' },
  { value: 'day', label: 'Dia' },
  { value: 'month', label: 'Mês' },
  { value: 'year', label: 'Ano' },
]

const GROUP_KEY_COLUMN_LABEL: Record<BudgetGroupBy, string> = {
  table: 'Tabela',
  user: 'Usuário',
  day: 'Dia',
  month: 'Mês',
  year: 'Ano',
}

function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

type GroupSortKey = 'key' | 'cost_usd' | 'billed_bytes' | 'job_count'

function compareGroup(a: CostGroup, b: CostGroup, key: GroupSortKey): number {
  if (key === 'key') return a.key.localeCompare(b.key)
  return a[key] - b[key]
}

type QuerySortKey = 'executed_at' | 'cost_usd' | 'billed_bytes'

function compareQuery(a: CostlyQuery, b: CostlyQuery, key: QuerySortKey): number {
  if (key === 'cost_usd') return a.cost_usd - b.cost_usd
  if (key === 'billed_bytes') return a.billed_bytes - b.billed_bytes
  return a.executed_at.localeCompare(b.executed_at)
}

export function BudgetPage() {
  const { projectId } = useProjectContext()
  const [groupBy, setGroupBy] = useState<BudgetGroupBy>('table')
  const query = useBudget(projectId, groupBy)
  const data = query.data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">FinOps — Budget de custo</h1>
          <p className="text-sm text-muted-foreground">
            Custo por agrupamento e queries mais caras do mês corrente — estimativa baseada em bytes
            escaneados, cobrança on-demand.
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

          <Tabs defaultValue={COST_TAB}>
            <TabsList className="w-fit">
              <TabsTrigger value={COST_TAB}>Custo por agrupamento</TabsTrigger>
              <TabsTrigger value={QUERIES_TAB}>Queries mais caras</TabsTrigger>
            </TabsList>

            <TabsContent value={COST_TAB}>
              <CostByGroupTab
                projectId={data.project_id}
                groups={data.groups}
                totalCostUsd={data.total_cost_usd}
                groupBy={groupBy}
                onGroupByChange={setGroupBy}
              />
            </TabsContent>

            <TabsContent value={QUERIES_TAB}>
              <QueriesTab queries={data.top_queries} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  )
}

function tableGroupLink(
  projectId: string,
  key: string,
): { datasetId: string; label: string } | null {
  if (!key.startsWith(`${projectId}.`)) return null
  const rest = key.slice(projectId.length + 1)
  const [datasetId] = rest.split('.')
  if (!datasetId) return null
  return { datasetId, label: rest }
}

function CostByGroupTab({
  projectId,
  groups,
  totalCostUsd,
  groupBy,
  onGroupByChange,
}: {
  projectId: string
  groups: CostGroup[]
  totalCostUsd: number
  groupBy: BudgetGroupBy
  onGroupByChange: (value: BudgetGroupBy) => void
}) {
  const {
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleGroups,
  } = useTableFilterSort<CostGroup, GroupSortKey>({
    rows: groups,
    initialSortKey: 'cost_usd',
    compare: compareGroup,
    matches: () => true,
  })

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex gap-2">
        {GROUP_BY_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onGroupByChange(option.value)}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              groupBy === option.value
                ? 'border-primary bg-primary/10 text-foreground'
                : 'border-border text-muted-foreground hover:bg-muted',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label={GROUP_KEY_COLUMN_LABEL[groupBy]}
              active={sortKey === 'key'}
              direction={sortDir}
              onClick={() => toggleSort('key')}
            />
            <SortableTableHead
              label="Bytes cobrados"
              active={sortKey === 'billed_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('billed_bytes')}
              align="right"
            />
            <SortableTableHead
              label="Jobs"
              active={sortKey === 'job_count'}
              direction={sortDir}
              onClick={() => toggleSort('job_count')}
              align="right"
            />
            <SortableTableHead
              label="Custo"
              active={sortKey === 'cost_usd'}
              direction={sortDir}
              onClick={() => toggleSort('cost_usd')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleGroups.map((group) => {
            const link = groupBy === 'table' ? tableGroupLink(projectId, group.key) : null
            return (
              <TableRow key={group.key}>
                <TableCell className="font-medium">
                  {link ? (
                    <Link to={`/datasets/${link.datasetId}`} className="hover:text-primary">
                      {link.label}
                    </Link>
                  ) : (
                    group.key
                  )}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatBytes(group.billed_bytes)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatNumber(group.job_count)}
                </TableCell>
                <TableCell className="text-right font-medium">
                  {formatUsd(group.cost_usd)}
                </TableCell>
              </TableRow>
            )
          })}
          {visibleGroups.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                Nenhum custo registrado neste mês.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
        {visibleGroups.length > 0 && (
          <TableFooter>
            <TableRow>
              <TableCell>Total</TableCell>
              <TableCell />
              <TableCell />
              <TableCell className="text-right">{formatUsd(totalCostUsd)}</TableCell>
            </TableRow>
          </TableFooter>
        )}
      </Table>
    </div>
  )
}

function QueriesTab({ queries }: { queries: CostlyQuery[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggleExpanded(jobId: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(jobId)) {
        next.delete(jobId)
      } else {
        next.add(jobId)
      }
      return next
    })
  }

  const {
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleQueries,
  } = useTableFilterSort<CostlyQuery, QuerySortKey>({
    rows: queries,
    initialSortKey: 'cost_usd',
    compare: compareQuery,
    matches: () => true,
  })

  return (
    <div className="mt-4 flex flex-col gap-4">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Custo"
              active={sortKey === 'cost_usd'}
              direction={sortDir}
              onClick={() => toggleSort('cost_usd')}
              align="right"
            />
            <TableHead>Usuário</TableHead>
            <SortableTableHead
              label="Data"
              active={sortKey === 'executed_at'}
              direction={sortDir}
              onClick={() => toggleSort('executed_at')}
            />
            <TableHead>Tabelas</TableHead>
            <SortableTableHead
              label="Bytes cobrados"
              active={sortKey === 'billed_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('billed_bytes')}
              align="right"
            />
            <TableHead>Query</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleQueries.map((q) => {
            const isExpanded = expanded.has(q.job_id)
            return (
              <Fragment key={q.job_id}>
                <TableRow>
                  <TableCell className="text-right font-medium">{formatUsd(q.cost_usd)}</TableCell>
                  <TableCell>{q.principal_email}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(q.executed_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex max-w-[220px] flex-wrap gap-1">
                      {q.tables.map((t) => (
                        <Badge key={t} variant="outline" className="truncate" title={t}>
                          {t.split('.').slice(1).join('.')}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatBytes(q.billed_bytes)}
                  </TableCell>
                  <TableCell>
                    {q.query_text ? (
                      <Button size="sm" variant="ghost" onClick={() => toggleExpanded(q.job_id)}>
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        {isExpanded ? 'Ocultar query' : 'Ver query'}
                      </Button>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
                {isExpanded && q.query_text && (
                  <TableRow>
                    <TableCell colSpan={6} className="bg-background/50">
                      <SqlPreview sql={q.query_text} defaultOpen />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            )
          })}
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
  )
}
