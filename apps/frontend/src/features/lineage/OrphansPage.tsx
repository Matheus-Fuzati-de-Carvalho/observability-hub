import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useOrphans } from '@/features/lineage/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import type { OrphanTable } from '@/types/lineage'

const DATASET_FILTER_ALL = 'all'

type SortKey = 'dataset_id' | 'table_id'

function compare(a: OrphanTable, b: OrphanTable, key: SortKey): number {
  return a[key].localeCompare(b[key])
}

export function OrphansPage() {
  const { projectId } = useProjectContext()
  const orphansQuery = useOrphans(projectId)
  const data = orphansQuery.data

  const datasets = useMemo(
    () => [...new Set(data?.orphans.map((o) => o.dataset_id) ?? [])].sort(),
    [data],
  )
  const [datasetFilter, setDatasetFilter] = useState(DATASET_FILTER_ALL)

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleOrphans,
  } = useTableFilterSort<OrphanTable, SortKey>({
    rows: data?.orphans ?? [],
    initialSortKey: 'dataset_id',
    compare,
    matches: (orphan, term) =>
      orphan.table_id.toLowerCase().includes(term.toLowerCase()) &&
      (datasetFilter === DATASET_FILTER_ALL || orphan.dataset_id === datasetFilter),
  })

  if (orphansQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (orphansQuery.isError) {
    return <ApiErrorNotice error={orphansQuery.error} />
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tabelas sem consumidor</h1>
          <p className="text-sm text-muted-foreground">
            {data.orphans.length} tabelas sem consumidor conhecido nos últimos {data.lookback_days}{' '}
            dias
          </p>
        </div>
        <RefreshButton
          isRefreshing={orphansQuery.isFetching}
          onRefresh={() => orphansQuery.refetch()}
        />
      </div>

      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por nome da tabela…"
            className="pl-8"
          />
        </div>
        <Select
          value={datasetFilter}
          onValueChange={(value) => setDatasetFilter(value ?? DATASET_FILTER_ALL)}
        >
          <SelectTrigger className="w-52">
            <SelectValue>
              {(value: string) => (value === DATASET_FILTER_ALL ? 'Todos os datasets' : value)}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={DATASET_FILTER_ALL}>Todos os datasets</SelectItem>
            {datasets.map((dataset) => (
              <SelectItem key={dataset} value={dataset}>
                {dataset}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
              label="Tabela"
              active={sortKey === 'table_id'}
              direction={sortDir}
              onClick={() => toggleSort('table_id')}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleOrphans.map((orphan) => (
            <TableRow key={`${data.project_id}.${orphan.dataset_id}.${orphan.table_id}`}>
              <TableCell>
                <Link to={`/datasets/${orphan.dataset_id}`} className="hover:text-primary">
                  {data.project_id}.{orphan.dataset_id}
                </Link>
              </TableCell>
              <TableCell className="font-medium">{orphan.table_id}</TableCell>
            </TableRow>
          ))}
          {visibleOrphans.length === 0 && (
            <TableRow>
              <TableCell colSpan={2} className="text-center text-muted-foreground">
                {data.orphans.length === 0
                  ? 'Nenhuma tabela sem consumidor encontrada.'
                  : 'Nenhuma tabela encontrada com esse filtro.'}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
