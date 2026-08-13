import { Layers, Sparkles } from 'lucide-react'
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
import { PartitionsDialog } from '@/features/catalog/PartitionsDialog'
import { ProfilingDialog } from '@/features/quality/ProfilingDialog'
import { formatBytes, formatDate, formatNumber } from '@/lib/format'
import type { TableSummary } from '@/types/catalog'

interface AssetsTableProps {
  projectId: string
  datasetId: string
  tables: TableSummary[]
}

function formatOrDash(value: string | null): string {
  return value ?? '—'
}

export function AssetsTable({ projectId, datasetId, tables }: AssetsTableProps) {
  const [profilingTarget, setProfilingTarget] = useState<string | null>(null)
  const [partitionsTarget, setPartitionsTarget] = useState<string | null>(null)
  const showPartitionColumns = tables.some((table) => table.is_partitioned)

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
            {showPartitionColumns && (
              <>
                <TableHead>Tipo de partição</TableHead>
                <TableHead>Partição mais antiga</TableHead>
                <TableHead>Partição mais recente</TableHead>
                <TableHead className="text-right">Qtd partições</TableHead>
              </>
            )}
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
              <TableCell>
                <div className="flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                  {table.is_partitioned && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPartitionsTarget(table.table_id)}
                    >
                      <Layers size={14} />
                      Ver partições
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setProfilingTarget(table.table_id)}
                  >
                    <Sparkles size={14} />
                    Analisar
                  </Button>
                </div>
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

      <PartitionsDialog
        projectId={projectId}
        datasetId={datasetId}
        tableId={partitionsTarget}
        onOpenChange={(open) => !open && setPartitionsTarget(null)}
      />
    </>
  )
}
