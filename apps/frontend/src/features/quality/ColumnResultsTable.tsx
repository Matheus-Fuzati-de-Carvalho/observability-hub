import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CompletenessBar } from '@/features/quality/CompletenessBar'
import { cn } from '@/lib/utils'
import type { ColumnProfile, QualityFlag, ScalarValue } from '@/types/profiling'

function formatScalar(value: ScalarValue): string {
  if (value === null) return '—'
  return String(value)
}

// distinct_pct alto = mais provável ser uma chave/id (alta cardinalidade);
// baixo = mais provável ser categórico (baixa cardinalidade).
const HIGH_CARDINALITY_THRESHOLD = 50

const QUALITY_FLAG_LABELS: Record<QualityFlag, string> = {
  ok: 'OK',
  warning: 'Atenção',
  critical: 'Crítico',
}

const QUALITY_FLAG_COLOR: Record<QualityFlag, string> = {
  ok: 'text-status-ok',
  warning: 'text-status-warn',
  critical: 'text-status-error',
}

export function ColumnResultsTable({ columns }: { columns: ColumnProfile[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Coluna</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead>Completude</TableHead>
          <TableHead>Unicidade (HLL)</TableHead>
          <TableHead>Min</TableHead>
          <TableHead>Max</TableHead>
          <TableHead>Tipo lógico</TableHead>
          <TableHead>Quality flag</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {columns.map((column) => (
          <TableRow key={column.column_name}>
            <TableCell className="font-medium">{column.column_name}</TableCell>
            <TableCell className="text-muted-foreground">{column.data_type}</TableCell>
            <TableCell>
              <CompletenessBar value={column.completeness_pct} flag={column.quality_flag} />
            </TableCell>
            <TableCell>
              <span
                className={cn(
                  'font-medium',
                  column.distinct_pct > HIGH_CARDINALITY_THRESHOLD
                    ? 'text-accent-purple'
                    : 'text-accent-orange',
                )}
              >
                {column.distinct_pct.toFixed(2)}%
              </span>
              <span className="ml-1 text-xs text-muted-foreground">({column.distinct_count})</span>
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatScalar(column.min_value)}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatScalar(column.max_value)}
            </TableCell>
            <TableCell>
              <Badge variant="outline">{column.inferred_logical_type}</Badge>
            </TableCell>
            <TableCell>
              <span className={cn('font-medium', QUALITY_FLAG_COLOR[column.quality_flag])}>
                {QUALITY_FLAG_LABELS[column.quality_flag]}
              </span>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
