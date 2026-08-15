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
import type { DatasetWithoutMatch } from '@/types/catalog'

type SortKey = 'dataset_id' | 'reason' | 'latest_partition'
type SortDirection = 'asc' | 'desc'

// Reasons conhecidos hoje (service.search_tables): "prefix_exists" (modes
// exact/contains — dataset tem outra tabela da mesma série) e "no_match"
// (mode not_contains — nenhuma tabela do dataset contém o termo).
const REASON_LABELS: Record<string, string> = {
  prefix_exists: 'Mesmo prefixo, partição diferente',
  no_match: 'Nenhuma tabela com o termo',
}

interface SearchAbsentTableProps {
  datasets: DatasetWithoutMatch[]
}

function compare(a: DatasetWithoutMatch, b: DatasetWithoutMatch, key: SortKey): number {
  if (key === 'latest_partition') {
    return (a.latest_partition ?? '').localeCompare(b.latest_partition ?? '')
  }
  return a[key].localeCompare(b[key])
}

export function SearchAbsentTable({ datasets }: SearchAbsentTableProps) {
  const [datasetFilter, setDatasetFilter] = useState('')
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
    const filtered = datasets.filter((d) =>
      d.dataset_id.toLowerCase().includes(datasetFilter.toLowerCase()),
    )
    const sign = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey))
  }, [datasets, datasetFilter, sortKey, sortDir])

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
            label="Motivo"
            active={sortKey === 'reason'}
            direction={sortDir}
            onClick={() => toggleSort('reason')}
          />
          <SortableTableHead
            label="Última partição encontrada"
            active={sortKey === 'latest_partition'}
            direction={sortDir}
            onClick={() => toggleSort('latest_partition')}
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
          <TableHead />
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.dataset_id}>
            <TableCell className="font-medium">{row.dataset_id}</TableCell>
            <TableCell>{REASON_LABELS[row.reason] ?? row.reason}</TableCell>
            <TableCell>{row.latest_partition ?? '—'}</TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && (
          <TableRow>
            <TableCell colSpan={3} className="text-center text-muted-foreground">
              Nenhum resultado com esse filtro.
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  )
}
