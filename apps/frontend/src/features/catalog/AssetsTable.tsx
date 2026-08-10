import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ProfilingDialog } from '@/features/quality/ProfilingDialog'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import type { TableSummary } from '@/types/catalog'

interface AssetsTableProps {
  projectId: string
  datasetId: string
  tables: TableSummary[]
}

export function AssetsTable({ projectId, datasetId, tables }: AssetsTableProps) {
  const [profilingTarget, setProfilingTarget] = useState<string | null>(null)

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nome</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead className="text-right">Colunas</TableHead>
            <TableHead>Criação</TableHead>
            <TableHead>Atualização</TableHead>
            <TableHead className="text-right">Linhas</TableHead>
            <TableHead className="text-right">Volume</TableHead>
            <TableHead>Região</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {tables.map((table) => (
            <TableRow key={table.table_id} className="group">
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
              <TableCell>
                <Button
                  size="sm"
                  variant="outline"
                  className="opacity-0 transition-opacity group-hover:opacity-100"
                  onClick={() => setProfilingTarget(table.table_id)}
                >
                  <Sparkles size={14} />
                  Analisar
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <ProfilingDialog
        projectId={projectId}
        datasetId={datasetId}
        tableId={profilingTarget}
        onOpenChange={(open) => !open && setProfilingTarget(null)}
      />
    </>
  )
}
