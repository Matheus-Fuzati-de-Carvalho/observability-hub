import { Search } from 'lucide-react'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useProfilingActivity } from '@/features/admin/hooks'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatDate, formatPercent } from '@/lib/format'
import type { ProfilingRunEntry } from '@/types/admin'

type SortKey =
  | 'table'
  | 'executed_by'
  | 'executed_at'
  | 'overall_density'
  | 'estimated_duplicate_pct'

function fullTableName(run: ProfilingRunEntry): string {
  return `${run.project_id}.${run.dataset_id}.${run.table_id}`
}

function compare(a: ProfilingRunEntry, b: ProfilingRunEntry, key: SortKey): number {
  if (key === 'table') return fullTableName(a).localeCompare(fullTableName(b))
  if (key === 'executed_by') return a.executed_by.localeCompare(b.executed_by)
  if (key === 'executed_at') return a.executed_at.localeCompare(b.executed_at)
  return a[key] - b[key]
}

export function ProfilingActivitySection() {
  const activityQuery = useProfilingActivity()

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleRuns,
  } = useTableFilterSort<ProfilingRunEntry, SortKey>({
    rows: activityQuery.data?.runs ?? [],
    initialSortKey: 'executed_at',
    compare,
    matches: (run, term) =>
      fullTableName(run).toLowerCase().includes(term.toLowerCase()) ||
      run.executed_by.toLowerCase().includes(term.toLowerCase()),
  })

  if (activityQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando atividade de profiling…</p>
  }

  if (activityQuery.isError || !activityQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar a atividade de profiling.</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-semibold text-lg">Atividade de profiling</h2>

      <div className="relative max-w-sm">
        <Search
          size={14}
          className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
        />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filtrar por tabela ou usuário…"
          className="pl-8"
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Tabela"
              active={sortKey === 'table'}
              direction={sortDir}
              onClick={() => toggleSort('table')}
            />
            <SortableTableHead
              label="Executado por"
              active={sortKey === 'executed_by'}
              direction={sortDir}
              onClick={() => toggleSort('executed_by')}
            />
            <SortableTableHead
              label="Quando"
              active={sortKey === 'executed_at'}
              direction={sortDir}
              onClick={() => toggleSort('executed_at')}
            />
            <SortableTableHead
              label="Densidade"
              active={sortKey === 'overall_density'}
              direction={sortDir}
              onClick={() => toggleSort('overall_density')}
              align="right"
            />
            <SortableTableHead
              label="Duplicatas"
              active={sortKey === 'estimated_duplicate_pct'}
              direction={sortDir}
              onClick={() => toggleSort('estimated_duplicate_pct')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleRuns.map((run) => (
            <TableRow key={`${fullTableName(run)}-${run.executed_at}`}>
              <TableCell className="font-medium">{fullTableName(run)}</TableCell>
              <TableCell className="text-muted-foreground">{run.executed_by}</TableCell>
              <TableCell className="text-muted-foreground">{formatDate(run.executed_at)}</TableCell>
              <TableCell className="text-right">{formatPercent(run.overall_density)}</TableCell>
              <TableCell className="text-right">
                {formatPercent(run.estimated_duplicate_pct)}
              </TableCell>
            </TableRow>
          ))}
          {visibleRuns.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="text-muted-foreground">
                Nenhum profiling executado ainda.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
