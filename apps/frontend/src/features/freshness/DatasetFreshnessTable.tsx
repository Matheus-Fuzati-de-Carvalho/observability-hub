import { Link, useParams } from 'react-router-dom'
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
import type { DatasetFreshnessSummary } from '@/types/freshness'

export function DatasetFreshnessTable({ datasets }: { datasets: DatasetFreshnessSummary[] }) {
  const { projectId } = useParams<{ projectId: string }>()

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Dataset</TableHead>
          <TableHead>Região</TableHead>
          <TableHead className="text-right">Tabelas</TableHead>
          {SLA_ORDER.map((status) => (
            <TableHead key={status} className="text-right">
              {SLA_SHORT_LABELS[status]}
            </TableHead>
          ))}
          <TableHead>Pior status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {datasets.map((dataset) => (
          <TableRow key={dataset.dataset_id}>
            <TableCell className="font-medium">
              <Link
                to={`/p/${projectId}/datasets/${dataset.dataset_id}`}
                className="hover:text-primary"
              >
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
      </TableBody>
    </Table>
  )
}
