import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { SLA_LABELS, SLA_ORDER, SLA_SHORT_LABELS, SLA_TEXT_COLOR } from '@/features/freshness/sla'
import { cn } from '@/lib/utils'
import type { DatasetFreshnessSummary, SLAStatus } from '@/types/freshness'

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

type SortKey = 'dataset_id' | 'location' | 'total_tables' | 'worst_status'
type SortDirection = 'asc' | 'desc'

function compare(a: DatasetFreshnessSummary, b: DatasetFreshnessSummary, key: SortKey): number {
  if (key === 'total_tables') return a.total_tables - b.total_tables
  if (key === 'worst_status') {
    const rank = (d: DatasetFreshnessSummary) =>
      d.worst_status ? SLA_ORDER.indexOf(d.worst_status) : -1
    return rank(a) - rank(b)
  }
  return a[key].localeCompare(b[key])
}

export function DatasetFreshnessTable({ datasets }: { datasets: DatasetFreshnessSummary[] }) {
  const [nameFilter, setNameFilter] = useState('')
  const [bucketFilter, setBucketFilter] = useState<SlaBucket | typeof SLA_BUCKET_FILTER_ALL>(
    SLA_BUCKET_FILTER_ALL,
  )
  const [sortKey, setSortKey] = useState<SortKey>('worst_status')
  const [sortDir, setSortDir] = useState<SortDirection>('desc')

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((direction) => (direction === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const visibleDatasets = useMemo(() => {
    const filtered = datasets.filter((dataset) => {
      const matchesName = dataset.dataset_id.toLowerCase().includes(nameFilter.toLowerCase())
      const matchesBucket =
        bucketFilter === SLA_BUCKET_FILTER_ALL ||
        (dataset.worst_status && SLA_BUCKET_BY_STATUS[dataset.worst_status] === bucketFilter)
      return matchesName && matchesBucket
    })
    const sign = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey))
  }, [datasets, nameFilter, bucketFilter, sortKey, sortDir])

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
            placeholder="Filtrar por dataset…"
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
              label="Dataset"
              active={sortKey === 'dataset_id'}
              direction={sortDir}
              onClick={() => toggleSort('dataset_id')}
            />
            <SortableTableHead
              label="Região"
              active={sortKey === 'location'}
              direction={sortDir}
              onClick={() => toggleSort('location')}
            />
            <SortableTableHead
              label="Tabelas"
              active={sortKey === 'total_tables'}
              direction={sortDir}
              onClick={() => toggleSort('total_tables')}
              align="right"
            />
            {SLA_ORDER.map((status) => (
              <TableHead key={status} className="text-right">
                {SLA_SHORT_LABELS[status]}
              </TableHead>
            ))}
            <SortableTableHead
              label="Pior status"
              active={sortKey === 'worst_status'}
              direction={sortDir}
              onClick={() => toggleSort('worst_status')}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleDatasets.map((dataset) => (
            <TableRow key={dataset.dataset_id}>
              <TableCell className="font-medium">
                <Link to={`/freshness/${dataset.dataset_id}`} className="hover:text-primary">
                  {dataset.dataset_id}
                </Link>
              </TableCell>
              <TableCell>{dataset.location}</TableCell>
              <TableCell className="text-right">{dataset.total_tables}</TableCell>
              {SLA_ORDER.map((status) => {
                const value = dataset[status]
                return (
                  <TableCell key={status} className="text-right">
                    {value > 0 ? (
                      <span className={cn('font-medium', SLA_TEXT_COLOR[status])}>{value}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                )
              })}
              <TableCell>
                {dataset.worst_status ? (
                  <span className={cn('font-medium', SLA_TEXT_COLOR[dataset.worst_status])}>
                    {SLA_LABELS[dataset.worst_status]}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
          {visibleDatasets.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={4 + SLA_ORDER.length}
                className="text-center text-muted-foreground"
              >
                Nenhum dataset encontrado com esse filtro.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </>
  )
}
