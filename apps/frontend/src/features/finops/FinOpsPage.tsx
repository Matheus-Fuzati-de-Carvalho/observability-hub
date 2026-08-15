import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { Badge } from '@/components/ui/badge'
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
import { usePartitionCandidates, useUnusedTables } from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import type { MinDaysUnused } from '@/types/finops'

const UNUSED_TAB = 'unused'
const PARTITION_TAB = 'partition'
const MIN_DAYS_OPTIONS: MinDaysUnused[] = [30, 60, 90]

function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

export function FinOpsPage() {
  const { projectId } = useProjectContext()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">FinOps — Scanner de desperdício</h1>
        <p className="text-sm text-muted-foreground">
          Tabelas sem uso e candidatas a particionamento, com estimativa de custo.
        </p>
      </div>

      <Tabs defaultValue={UNUSED_TAB}>
        <TabsList className="w-fit">
          <TabsTrigger value={UNUSED_TAB}>Tabelas sem uso</TabsTrigger>
          <TabsTrigger value={PARTITION_TAB}>Candidatas a particionamento</TabsTrigger>
        </TabsList>

        <TabsContent value={UNUSED_TAB}>
          <UnusedTablesTab projectId={projectId} />
        </TabsContent>

        <TabsContent value={PARTITION_TAB}>
          <PartitionCandidatesTab projectId={projectId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function UnusedTablesTab({ projectId }: { projectId: string | undefined }) {
  const [minDaysUnused, setMinDaysUnused] = useState<MinDaysUnused>(30)
  const query = useUnusedTables(projectId, minDaysUnused)

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

  const data = query.data
  if (!data) return null

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
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
          <span className="text-sm text-muted-foreground">
            — {data.tables.length} tabela{data.tables.length === 1 ? '' : 's'}
          </span>
        </div>
        <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
      </div>

      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tabela</TableHead>
            <TableHead className="text-right">Tamanho</TableHead>
            <TableHead>Último acesso</TableHead>
            <TableHead className="text-right">Custo de storage estimado/mês</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.tables.map((table) => (
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
                {table.last_accessed_at ? formatDate(table.last_accessed_at) : 'Nunca (na janela)'}
              </TableCell>
              <TableCell className="text-right font-medium">
                {formatUsd(table.estimated_monthly_storage_cost_usd)}
              </TableCell>
            </TableRow>
          ))}
          {data.tables.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                Nenhuma tabela sem uso encontrada.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

function PartitionCandidatesTab({ projectId }: { projectId: string | undefined }) {
  const query = usePartitionCandidates(projectId)

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

  const data = query.data
  if (!data) return null

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data.candidates.length} candidata{data.candidates.length === 1 ? '' : 's'} — custo
          observado nos últimos {data.lookback_days} dias
        </p>
        <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
      </div>

      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tabela</TableHead>
            <TableHead className="text-right">Tamanho</TableHead>
            <TableHead>Coluna candidata</TableHead>
            <TableHead className="text-right">Custo observado (30d)</TableHead>
            <TableHead className="text-right">Economia estimada</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.candidates.map((candidate) => (
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
          {data.candidates.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                Nenhuma candidata a particionamento encontrada.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
