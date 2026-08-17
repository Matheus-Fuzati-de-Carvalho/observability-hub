import { Search } from 'lucide-react'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { PaginationBar } from '@/components/PaginationBar'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { usePiiScanActivity } from '@/features/admin/hooks'
import { usePagination } from '@/hooks/usePagination'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatDate } from '@/lib/format'
import type { PiiScanEntry } from '@/types/admin'

type SortKey =
  | 'project'
  | 'dataset'
  | 'table'
  | 'executed_by'
  | 'executed_at'
  | 'flagged_columns_count'

function fullTableName(scan: PiiScanEntry): string {
  return `${scan.project_id}.${scan.dataset_id}.${scan.table_id}`
}

function compare(a: PiiScanEntry, b: PiiScanEntry, key: SortKey): number {
  if (key === 'project') return a.project_id.localeCompare(b.project_id)
  if (key === 'dataset') return a.dataset_id.localeCompare(b.dataset_id)
  if (key === 'table') return a.table_id.localeCompare(b.table_id)
  if (key === 'executed_by') return a.executed_by.localeCompare(b.executed_by)
  if (key === 'executed_at') return a.executed_at.localeCompare(b.executed_at)
  return a.flagged_columns_count - b.flagged_columns_count
}

export function PiiScanActivitySection() {
  const activityQuery = usePiiScanActivity()

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleScans,
  } = useTableFilterSort<PiiScanEntry, SortKey>({
    rows: activityQuery.data?.scans ?? [],
    initialSortKey: 'executed_at',
    compare,
    matches: (scan, term) => {
      const t = term.toLowerCase()
      return (
        scan.project_id.toLowerCase().includes(t) ||
        scan.dataset_id.toLowerCase().includes(t) ||
        scan.table_id.toLowerCase().includes(t) ||
        scan.executed_by.toLowerCase().includes(t)
      )
    },
  })

  const pagination = usePagination({ rowCount: visibleScans.length })
  const pageScans = visibleScans.slice(pagination.start, pagination.end)

  if (activityQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando scans de PII…</p>
  }

  if (activityQuery.isError || !activityQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar os scans de PII.</p>
  }

  return (
    <CollapsibleSection title="Scans de PII">
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
                label="Colunas sinalizadas"
                active={sortKey === 'flagged_columns_count'}
                direction={sortDir}
                onClick={() => toggleSort('flagged_columns_count')}
                align="right"
              />
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageScans.map((scan) => (
              <TableRow key={`${fullTableName(scan)}-${scan.executed_at}`}>
                <TableCell className="font-medium">{scan.project_id}</TableCell>
                <TableCell className="font-medium">{scan.dataset_id}</TableCell>
                <TableCell className="font-medium">{scan.table_id}</TableCell>
                <TableCell className="text-muted-foreground">{scan.executed_by}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(scan.executed_at)}
                </TableCell>
                <TableCell className="text-right">{scan.flagged_columns_count}</TableCell>
              </TableRow>
            ))}
            {visibleScans.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-muted-foreground">
                  Nenhum scan de PII executado ainda.
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
        totalCount={visibleScans.length}
        onPrevious={pagination.goToPreviousPage}
        onNext={pagination.goToNextPage}
      />
    </CollapsibleSection>
  )
}
