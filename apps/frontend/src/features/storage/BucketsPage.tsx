import { Search } from 'lucide-react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useBuckets } from '@/features/storage/hooks'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import type { BucketSummary } from '@/types/storage'

type SortKey =
  | 'name'
  | 'location'
  | 'storage_class'
  | 'total_size_bytes'
  | 'object_count'
  | 'time_created'
  | 'updated'

function compare(a: BucketSummary, b: BucketSummary, key: SortKey): number {
  if (key === 'total_size_bytes' || key === 'object_count') {
    return a[key] - b[key]
  }
  return a[key].localeCompare(b[key])
}

export function BucketsPage() {
  const { projectId } = useProjectContext()
  const bucketsQuery = useBuckets(projectId)
  const data = bucketsQuery.data

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleBuckets,
  } = useTableFilterSort<BucketSummary, SortKey>({
    rows: data?.buckets ?? [],
    initialSortKey: 'name',
    compare,
    matches: (bucket, term) => bucket.name.toLowerCase().includes(term.toLowerCase()),
  })

  if (bucketsQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (bucketsQuery.isError) {
    return <ApiErrorNotice error={bucketsQuery.error} />
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Buckets</h1>
          <p className="text-sm text-muted-foreground">{data.buckets.length} buckets</p>
        </div>
        <RefreshButton
          isRefreshing={bucketsQuery.isFetching}
          onRefresh={() => bucketsQuery.refetch()}
        />
      </div>

      <div className="relative min-w-[220px] max-w-sm">
        <Search
          size={14}
          className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
        />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filtrar por nome do bucket…"
          className="pl-8"
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Nome"
              active={sortKey === 'name'}
              direction={sortDir}
              onClick={() => toggleSort('name')}
            />
            <SortableTableHead
              label="Localização"
              active={sortKey === 'location'}
              direction={sortDir}
              onClick={() => toggleSort('location')}
            />
            <SortableTableHead
              label="Storage class"
              active={sortKey === 'storage_class'}
              direction={sortDir}
              onClick={() => toggleSort('storage_class')}
            />
            <SortableTableHead
              label="Tamanho"
              active={sortKey === 'total_size_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('total_size_bytes')}
              align="right"
            />
            <SortableTableHead
              label="Objetos"
              active={sortKey === 'object_count'}
              direction={sortDir}
              onClick={() => toggleSort('object_count')}
              align="right"
            />
            <TableHead>Lifecycle rule</TableHead>
            <SortableTableHead
              label="Criado em"
              active={sortKey === 'time_created'}
              direction={sortDir}
              onClick={() => toggleSort('time_created')}
            />
            <SortableTableHead
              label="Atualizado em"
              active={sortKey === 'updated'}
              direction={sortDir}
              onClick={() => toggleSort('updated')}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleBuckets.map((bucket) => (
            <TableRow key={bucket.name}>
              <TableCell className="font-medium">{bucket.name}</TableCell>
              <TableCell>{bucket.location}</TableCell>
              <TableCell>
                <Badge variant="secondary">{bucket.storage_class}</Badge>
              </TableCell>
              <TableCell className="text-right">{formatBytes(bucket.total_size_bytes)}</TableCell>
              <TableCell className="text-right">{formatNumber(bucket.object_count)}</TableCell>
              <TableCell>
                {bucket.has_lifecycle_rule ? (
                  <Badge variant="secondary">Configurada</Badge>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell>{formatDate(bucket.time_created)}</TableCell>
              <TableCell>{formatDate(bucket.updated)}</TableCell>
            </TableRow>
          ))}
          {visibleBuckets.length === 0 && (
            <TableRow>
              <TableCell colSpan={8} className="text-center text-muted-foreground">
                {data.buckets.length === 0
                  ? 'Nenhum bucket encontrado neste projeto.'
                  : 'Nenhum bucket encontrado com esse filtro.'}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
