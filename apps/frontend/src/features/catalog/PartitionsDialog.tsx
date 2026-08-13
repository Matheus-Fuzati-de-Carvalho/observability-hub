import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useTablePartitions } from '@/features/catalog/hooks'
import { formatNumber } from '@/lib/format'
import { ApiError } from '@/lib/http-client'

interface PartitionsDialogProps {
  projectId: string
  datasetId: string
  tableId: string | null
  onOpenChange: (open: boolean) => void
}

export function PartitionsDialog({
  projectId,
  datasetId,
  tableId,
  onOpenChange,
}: PartitionsDialogProps) {
  const partitionsQuery = useTablePartitions(projectId, datasetId, tableId ?? undefined)
  const errorMessage =
    partitionsQuery.error instanceof ApiError
      ? partitionsQuery.error.message
      : partitionsQuery.error instanceof Error
        ? partitionsQuery.error.message
        : null

  return (
    <Dialog open={Boolean(tableId)} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] w-[90vw]! max-w-[600px]! overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Partições de {datasetId}.{tableId}
          </DialogTitle>
          <DialogDescription>
            {partitionsQuery.data
              ? `Particionada por ${partitionsQuery.data.partition_type}`
              : 'Carregando…'}
          </DialogDescription>
        </DialogHeader>

        {partitionsQuery.isLoading && (
          <p className="text-sm text-muted-foreground">Carregando partições…</p>
        )}

        {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}

        {partitionsQuery.data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Valor da partição</TableHead>
                <TableHead className="text-right">Qtd linhas</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {partitionsQuery.data.partitions.map((partition) => (
                <TableRow key={partition.value}>
                  <TableCell className="font-medium">{partition.value}</TableCell>
                  <TableCell className="text-right">{formatNumber(partition.row_count)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TableCell>Total de partições</TableCell>
                <TableCell className="text-right">
                  {formatNumber(partitionsQuery.data.total_partitions)}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        )}
      </DialogContent>
    </Dialog>
  )
}
