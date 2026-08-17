import { Search } from 'lucide-react'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { usePiiScanActivity } from '@/features/admin/hooks'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatDate } from '@/lib/format'
import type { PiiScanEntry } from '@/types/admin'

type SortKey = 'table' | 'executed_by' | 'executed_at' | 'flagged_columns_count'

function fullTableName(scan: PiiScanEntry): string {
  return `${scan.project_id}.${scan.dataset_id}.${scan.table_id}`
}

function compare(a: PiiScanEntry, b: PiiScanEntry, key: SortKey): number {
  if (key === 'table') return fullTableName(a).localeCompare(fullTableName(b))
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
    matches: (scan, term) =>
      fullTableName(scan).toLowerCase().includes(term.toLowerCase()) ||
      scan.executed_by.toLowerCase().includes(term.toLowerCase()),
  })

  if (activityQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando scans de PII…</p>
  }

  if (activityQuery.isError || !activityQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar os scans de PII.</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-semibold text-lg">Scans de PII</h2>

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
              label="Colunas sinalizadas"
              active={sortKey === 'flagged_columns_count'}
              direction={sortDir}
              onClick={() => toggleSort('flagged_columns_count')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleScans.map((scan) => (
            <TableRow key={`${fullTableName(scan)}-${scan.executed_at}`}>
              <TableCell className="font-medium">{fullTableName(scan)}</TableCell>
              <TableCell className="text-muted-foreground">{scan.executed_by}</TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(scan.executed_at)}
              </TableCell>
              <TableCell className="text-right">{scan.flagged_columns_count}</TableCell>
            </TableRow>
          ))}
          {visibleScans.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-muted-foreground">
                Nenhum scan de PII executado ainda.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
