import { Search } from 'lucide-react'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { PaginationBar } from '@/components/PaginationBar'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useProfilingActivity } from '@/features/admin/hooks'
import { usePagination } from '@/hooks/usePagination'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatDate, formatPercent } from '@/lib/format'
import type { ProfilingRunEntry } from '@/types/admin'

type SortKey =
  | 'project'
  | 'dataset'
  | 'table'
  | 'executed_by'
  | 'executed_at'
  | 'overall_density'
  | 'estimated_duplicate_pct'

function fullTableName(run: ProfilingRunEntry): string {
  return `${run.project_id}.${run.dataset_id}.${run.table_id}`
}

function compare(a: ProfilingRunEntry, b: ProfilingRunEntry, key: SortKey): number {
  if (key === 'project') return a.project_id.localeCompare(b.project_id)
  if (key === 'dataset') return a.dataset_id.localeCompare(b.dataset_id)
  if (key === 'table') return a.table_id.localeCompare(b.table_id)
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
    matches: (run, term) => {
      const t = term.toLowerCase()
      return (
        run.project_id.toLowerCase().includes(t) ||
        run.dataset_id.toLowerCase().includes(t) ||
        run.table_id.toLowerCase().includes(t) ||
        run.executed_by.toLowerCase().includes(t)
      )
    },
  })

  const pagination = usePagination({ rowCount: visibleRuns.length })
  const pageRuns = visibleRuns.slice(pagination.start, pagination.end)

  if (activityQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando atividade de profiling…</p>
  }

  if (activityQuery.isError || !activityQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar a atividade de profiling.</p>
  }

  return (
    <CollapsibleSection title="Atividade de profiling">
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

      <div className="max-h-[420px] overflow-y-auto rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableTableHead
                label="Projeto"
                active={sortKey === 'project'}
                direction={sortDir}
                onClick={() => toggleSort('project')}
              />
              <SortableTableHead
                label="Dataset"
                active={sortKey === 'dataset'}
                direction={sortDir}
                onClick={() => toggleSort('dataset')}
              />
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
            {pageRuns.map((run) => (
              <TableRow key={`${fullTableName(run)}-${run.executed_at}`}>
                <TableCell className="font-medium">{run.project_id}</TableCell>
                <TableCell className="font-medium">{run.dataset_id}</TableCell>
                <TableCell className="font-medium">{run.table_id}</TableCell>
                <TableCell className="text-muted-foreground">{run.executed_by}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(run.executed_at)}
                </TableCell>
                <TableCell className="text-right">{formatPercent(run.overall_density)}</TableCell>
                <TableCell className="text-right">
                  {formatPercent(run.estimated_duplicate_pct)}
                </TableCell>
              </TableRow>
            ))}
            {visibleRuns.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-muted-foreground">
                  Nenhum profiling executado ainda.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <PaginationBar
        page={pagination.page}
        pageCount={pagination.pageCount}
        pageSize={pagination.pageSize}
        setPageSize={pagination.setPageSize}
        start={pagination.start}
        end={pagination.end}
        totalCount={visibleRuns.length}
        onPrevious={pagination.goToPreviousPage}
        onNext={pagination.goToNextPage}
      />
    </CollapsibleSection>
  )
}
