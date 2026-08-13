import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { SLA_LABELS, SLA_ORDER, SLA_TEXT_COLOR } from '@/features/freshness/sla'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { SLAStatus, TableFreshness } from '@/types/freshness'

type SlaBucket = 'ok' | 'warning' | 'stale'
const SLA_BUCKET_FILTER_ALL = 'all'

// Mesmo agrupamento visual já usado em toda a app (SLA_TEXT_COLOR) — verde/
// amarelo/vermelho, não os 6 status granulares um a um.
const SLA_BUCKET_BY_STATUS: Record<SLAStatus, SlaBucket> = SLA_ORDER.reduce(
  (acc, status) => {
    const color = SLA_TEXT_COLOR[status]
    acc[status] =
      color === 'text-status-ok' ? 'ok' : color === 'text-status-warn' ? 'warning' : 'stale'
    return acc
  },
  {} as Record<SLAStatus, SlaBucket>,
)

const SLA_BUCKET_LABELS: Record<SlaBucket, string> = {
  ok: 'Ok',
  warning: 'Alerta',
  stale: 'Obsoleta',
}

const SLA_BUCKET_DOT_COLOR: Record<SlaBucket, string> = {
  ok: 'bg-status-ok',
  warning: 'bg-status-warn',
  stale: 'bg-status-error',
}

type SortKey =
  | 'table_id'
  | 'last_modified_time'
  | 'hours_since_update'
  | 'sla_status'
  | 'row_count'
  | 'size_bytes'
type SortDirection = 'asc' | 'desc'

function compare(a: TableFreshness, b: TableFreshness, key: SortKey): number {
  if (key === 'hours_since_update') {
    return (a.hours_since_update ?? -1) - (b.hours_since_update ?? -1)
  }
  if (key === 'row_count') return (a.row_count ?? -1) - (b.row_count ?? -1)
  if (key === 'size_bytes') return (a.size_bytes ?? -1) - (b.size_bytes ?? -1)
  if (key === 'last_modified_time') {
    return (a.last_modified_time ?? '').localeCompare(b.last_modified_time ?? '')
  }
  if (key === 'sla_status') {
    const rank = (s: TableFreshness) => (s.sla_status ? SLA_ORDER.indexOf(s.sla_status) : -1)
    return rank(a) - rank(b)
  }
  return a[key].localeCompare(b[key])
}

export function TableFreshnessTable({ tables }: { tables: TableFreshness[] }) {
  const [nameFilter, setNameFilter] = useState('')
  const [bucketFilter, setBucketFilter] = useState<SlaBucket | typeof SLA_BUCKET_FILTER_ALL>(
    SLA_BUCKET_FILTER_ALL,
  )
  const [sortKey, setSortKey] = useState<SortKey>('sla_status')
  const [sortDir, setSortDir] = useState<SortDirection>('desc')

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((direction) => (direction === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const visibleTables = useMemo(() => {
    const filtered = tables.filter((table) => {
      const matchesName = table.table_id.toLowerCase().includes(nameFilter.toLowerCase())
      const matchesBucket =
        bucketFilter === SLA_BUCKET_FILTER_ALL ||
        (table.sla_status && SLA_BUCKET_BY_STATUS[table.sla_status] === bucketFilter)
      return matchesName && matchesBucket
    })
    const sign = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey))
  }, [tables, nameFilter, bucketFilter, sortKey, sortDir])

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={nameFilter}
            onChange={(e) => setNameFilter(e.target.value)}
            placeholder="Filtrar por nome…"
            className="pl-8"
          />
        </div>
        <div className="flex gap-2">
          {(['all', 'ok', 'warning', 'stale'] as const).map((bucket) => (
            <button
              key={bucket}
              type="button"
              onClick={() => setBucketFilter(bucket)}
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                bucketFilter === bucket
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border text-muted-foreground hover:bg-muted',
              )}
            >
              {bucket !== 'all' && (
                <span className={cn('size-2 rounded-full', SLA_BUCKET_DOT_COLOR[bucket])} />
              )}
              {bucket === 'all' ? 'Todos' : SLA_BUCKET_LABELS[bucket]}
            </button>
          ))}
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Nome"
              active={sortKey === 'table_id'}
              direction={sortDir}
              onClick={() => toggleSort('table_id')}
            />
            <SortableTableHead
              label="Última atualização"
              active={sortKey === 'last_modified_time'}
              direction={sortDir}
              onClick={() => toggleSort('last_modified_time')}
            />
            <SortableTableHead
              label="Horas desde atualização"
              active={sortKey === 'hours_since_update'}
              direction={sortDir}
              onClick={() => toggleSort('hours_since_update')}
              align="right"
            />
            <SortableTableHead
              label="Status SLA"
              active={sortKey === 'sla_status'}
              direction={sortDir}
              onClick={() => toggleSort('sla_status')}
            />
            <SortableTableHead
              label="Linhas"
              active={sortKey === 'row_count'}
              direction={sortDir}
              onClick={() => toggleSort('row_count')}
              align="right"
            />
            <SortableTableHead
              label="Volume"
              active={sortKey === 'size_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('size_bytes')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleTables.map((table) => (
            <TableRow key={table.table_id}>
              <TableCell className="font-medium">{table.table_id}</TableCell>
              <TableCell>{formatDate(table.last_modified_time)}</TableCell>
              <TableCell className="text-right">
                {table.hours_since_update === null ? '—' : formatNumber(table.hours_since_update)}
              </TableCell>
              <TableCell>
                {table.sla_status ? (
                  <span className={cn('font-medium', SLA_TEXT_COLOR[table.sla_status])}>
                    {SLA_LABELS[table.sla_status]}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="text-right">{formatNumber(table.row_count)}</TableCell>
              <TableCell className="text-right">{formatBytes(table.size_bytes)}</TableCell>
            </TableRow>
          ))}
          {visibleTables.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground">
                Nenhuma tabela encontrada com esse filtro.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </>
  )
}
