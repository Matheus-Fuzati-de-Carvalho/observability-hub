import { useMemo, useState } from 'react'
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
import { formatDate, formatNumber } from '@/lib/format'
import type { DatasetWithMatch } from '@/types/catalog'

type SortKey = 'dataset_id' | 'table_id' | 'last_modified_time' | 'row_count'
type SortDirection = 'asc' | 'desc'

interface SearchMatchesTableProps {
  matches: DatasetWithMatch[]
}

function compare(a: DatasetWithMatch, b: DatasetWithMatch, key: SortKey): number {
  if (key === 'row_count') return (a.row_count ?? -1) - (b.row_count ?? -1)
  if (key === 'last_modified_time') {
    return (a.last_modified_time ?? '').localeCompare(b.last_modified_time ?? '')
  }
  return a[key].localeCompare(b[key])
}

export function SearchMatchesTable({ matches }: SearchMatchesTableProps) {
  const [datasetFilter, setDatasetFilter] = useState('')
  const [tableFilter, setTableFilter] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('dataset_id')
  const [sortDir, setSortDir] = useState<SortDirection>('asc')

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((direction) => (direction === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const rows = useMemo(() => {
    const filtered = matches.filter(
      (m) =>
        m.dataset_id.toLowerCase().includes(datasetFilter.toLowerCase()) &&
        m.table_id.toLowerCase().includes(tableFilter.toLowerCase()),
    )
    const sign = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey))
  }, [matches, datasetFilter, tableFilter, sortKey, sortDir])

  return (
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
          <SortableTableHead
            label="Atualizado em"
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
        </TableRow>
        <TableRow>
          <TableHead>
            <Input
              value={datasetFilter}
              onChange={(e) => setDatasetFilter(e.target.value)}
              placeholder="Filtrar dataset…"
              className="h-7 text-xs"
            />
          </TableHead>
          <TableHead>
            <Input
              value={tableFilter}
              onChange={(e) => setTableFilter(e.target.value)}
              placeholder="Filtrar tabela…"
              className="h-7 text-xs"
            />
          </TableHead>
          <TableHead />
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.dataset_id}.${row.table_id}`}>
            <TableCell className="font-medium">{row.dataset_id}</TableCell>
            <TableCell>{row.table_id}</TableCell>
            <TableCell>{formatDate(row.last_modified_time)}</TableCell>
            <TableCell className="text-right">{formatNumber(row.row_count)}</TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && (
          <TableRow>
            <TableCell colSpan={4} className="text-center text-muted-foreground">
              Nenhum resultado com esse filtro.
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  )
}
