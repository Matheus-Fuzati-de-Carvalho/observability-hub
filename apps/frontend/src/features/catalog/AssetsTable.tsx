import { Layers, Search, Sparkles, Star } from 'lucide-react'
import { useMemo, useState } from 'react'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { PartitionsDialog } from '@/features/catalog/PartitionsDialog'
import { isFavoriteTable, useFavorites, useToggleFavorite } from '@/features/favorites/hooks'
import { useRecordTableView } from '@/features/history/hooks'
import { ProfilingDialog } from '@/features/quality/ProfilingDialog'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { TableSummary, TableType } from '@/types/catalog'

const TYPE_FILTER_ALL = 'all'
const TYPE_LABELS: Record<TableType, string> = {
  TABLE: 'TABLE',
  VIEW: 'VIEW',
  EXTERNAL: 'EXTERNAL',
  MATERIALIZED_VIEW: 'MATERIALIZED_VIEW',
}

type SortKey =
  | 'table_id'
  | 'table_type'
  | 'column_count'
  | 'creation_time'
  | 'last_modified_time'
  | 'row_count'
  | 'size_bytes'
type SortDirection = 'asc' | 'desc'

interface AssetsTableProps {
  projectId: string
  datasetId: string
  tables: TableSummary[]
  highlightTableId?: string | null
}

function formatOrDash(value: string | null): string {
  return value ?? '—'
}

function compare(a: TableSummary, b: TableSummary, key: SortKey): number {
  if (key === 'column_count') return a.column_count - b.column_count
  if (key === 'row_count') return (a.row_count ?? -1) - (b.row_count ?? -1)
  if (key === 'size_bytes') return (a.size_bytes ?? -1) - (b.size_bytes ?? -1)
  if (key === 'last_modified_time') {
    return (a.last_modified_time ?? '').localeCompare(b.last_modified_time ?? '')
  }
  return a[key].localeCompare(b[key])
}

export function AssetsTable({ projectId, datasetId, tables, highlightTableId }: AssetsTableProps) {
  const [profilingTarget, setProfilingTarget] = useState<string | null>(null)
  const [partitionsTarget, setPartitionsTarget] = useState<string | null>(null)
  const [nameFilter, setNameFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState<TableType | typeof TYPE_FILTER_ALL>(TYPE_FILTER_ALL)
  const [sortKey, setSortKey] = useState<SortKey>('table_id')
  const [sortDir, setSortDir] = useState<SortDirection>('asc')
  const favoritesQuery = useFavorites()
  const toggleFavorite = useToggleFavorite()
  const recordTableView = useRecordTableView()

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((direction) => (direction === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const visibleTables = useMemo(() => {
    const filtered = tables.filter(
      (table) =>
        table.table_id.toLowerCase().includes(nameFilter.toLowerCase()) &&
        (typeFilter === TYPE_FILTER_ALL || table.table_type === typeFilter),
    )
    const sign = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey))
  }, [tables, nameFilter, typeFilter, sortKey, sortDir])

  const showPartitionColumns = tables.some((table) => table.is_partitioned)

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
        <Select
          value={typeFilter}
          onValueChange={(value) => setTypeFilter((value as TableType) ?? TYPE_FILTER_ALL)}
        >
          <SelectTrigger className="w-44">
            <SelectValue>
              {(value: TableType | typeof TYPE_FILTER_ALL) =>
                value === TYPE_FILTER_ALL ? 'Todos os tipos' : TYPE_LABELS[value]
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TYPE_FILTER_ALL}>Todos os tipos</SelectItem>
            <SelectItem value="TABLE">TABLE</SelectItem>
            <SelectItem value="VIEW">VIEW</SelectItem>
            <SelectItem value="EXTERNAL">EXTERNAL</SelectItem>
            <SelectItem value="MATERIALIZED_VIEW">MATERIALIZED_VIEW</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead />
            <TableHead>Ações</TableHead>
            <SortableTableHead
              label="Nome"
              active={sortKey === 'table_id'}
              direction={sortDir}
              onClick={() => toggleSort('table_id')}
            />
            <SortableTableHead
              label="Tipo"
              active={sortKey === 'table_type'}
              direction={sortDir}
              onClick={() => toggleSort('table_type')}
            />
            <SortableTableHead
              label="Colunas"
              active={sortKey === 'column_count'}
              direction={sortDir}
              onClick={() => toggleSort('column_count')}
              align="right"
            />
            <SortableTableHead
              label="Criação"
              active={sortKey === 'creation_time'}
              direction={sortDir}
              onClick={() => toggleSort('creation_time')}
            />
            <SortableTableHead
              label="Atualização"
              active={sortKey === 'last_modified_time'}
              direction={sortDir}
              onClick={() => toggleSort('last_modified_time')}
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
            <TableHead>Região</TableHead>
            {showPartitionColumns && (
              <>
                <TableHead>Tipo de partição</TableHead>
                <TableHead>Partição mais antiga</TableHead>
                <TableHead>Partição mais recente</TableHead>
                <TableHead className="text-right">Qtd partições</TableHead>
              </>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleTables.map((table) => {
            const isFavorite = isFavoriteTable(
              favoritesQuery.data,
              projectId,
              datasetId,
              table.table_id,
            )
            return (
              <TableRow
                key={table.table_id}
                className={cn(highlightTableId === table.table_id && 'bg-primary/10')}
              >
                <TableCell>
                  <button
                    type="button"
                    onClick={() =>
                      toggleFavorite.mutate({
                        projectId,
                        datasetId,
                        tableId: table.table_id,
                        isFavorite,
                      })
                    }
                    aria-label={isFavorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}
                    className="text-muted-foreground hover:text-primary"
                  >
                    <Star
                      size={16}
                      className={isFavorite ? 'fill-primary text-primary' : undefined}
                    />
                  </button>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Tooltip>
                      <TooltipTrigger
                        render={
                          <Button
                            size="sm"
                            variant="outline"
                            aria-disabled={!table.is_partitioned}
                            className={cn(
                              !table.is_partitioned &&
                                'cursor-not-allowed text-muted-foreground opacity-50 hover:bg-background',
                            )}
                            onClick={() =>
                              table.is_partitioned && setPartitionsTarget(table.table_id)
                            }
                          />
                        }
                      >
                        <Layers size={14} />
                        Ver partições
                      </TooltipTrigger>
                      {!table.is_partitioned && (
                        <TooltipContent>Tabela não particionada</TooltipContent>
                      )}
                    </Tooltip>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        recordTableView.mutate({ projectId, datasetId, tableId: table.table_id })
                        setProfilingTarget(table.table_id)
                      }}
                    >
                      <Sparkles size={14} />
                      Analisar
                    </Button>
                  </div>
                </TableCell>
                <TableCell className="font-medium">{table.table_id}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{table.table_type}</Badge>
                </TableCell>
                <TableCell className="text-right">{table.column_count}</TableCell>
                <TableCell>{formatDate(table.creation_time)}</TableCell>
                <TableCell>{formatDate(table.last_modified_time)}</TableCell>
                <TableCell className="text-right">{formatNumber(table.row_count)}</TableCell>
                <TableCell className="text-right">{formatBytes(table.size_bytes)}</TableCell>
                <TableCell>{table.location}</TableCell>
                {showPartitionColumns && (
                  <>
                    <TableCell>
                      {table.is_partitioned ? formatOrDash(table.partition_type) : null}
                    </TableCell>
                    <TableCell>
                      {table.is_partitioned ? formatOrDash(table.min_partition) : null}
                    </TableCell>
                    <TableCell>
                      {table.is_partitioned ? formatOrDash(table.max_partition) : null}
                    </TableCell>
                    <TableCell className="text-right">
                      {table.is_partitioned ? formatNumber(table.partition_count) : null}
                    </TableCell>
                  </>
                )}
              </TableRow>
            )
          })}
          {visibleTables.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={showPartitionColumns ? 13 : 9}
                className="text-center text-muted-foreground"
              >
                Nenhuma tabela encontrada com esse filtro.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <ProfilingDialog
        projectId={projectId}
        datasetId={datasetId}
        tableId={profilingTarget}
        onOpenChange={(open) => !open && setProfilingTarget(null)}
      />

      <PartitionsDialog
        projectId={projectId}
        datasetId={datasetId}
        tableId={partitionsTarget}
        onOpenChange={(open) => !open && setPartitionsTarget(null)}
      />
    </>
  )
}
