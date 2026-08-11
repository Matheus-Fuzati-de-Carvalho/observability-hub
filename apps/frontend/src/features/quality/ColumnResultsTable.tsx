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
          <TableHead className="text-xs">Coluna</TableHead>
          <TableHead className="text-xs">Tipo</TableHead>
          <TableHead className="text-xs">Completude</TableHead>
          <TableHead className="text-xs">Unicidade (HLL)</TableHead>
          <TableHead className="text-xs">Min</TableHead>
          <TableHead className="text-xs">Max</TableHead>
          <TableHead className="text-xs">Tipo lógico</TableHead>
          <TableHead className="text-xs">Quality flag</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {columns.map((column) => (
          <TableRow key={column.column_name}>
            <TableCell className="text-xs font-medium">{column.column_name}</TableCell>
            <TableCell className="text-xs text-muted-foreground">{column.data_type}</TableCell>
            <TableCell className="text-xs">
              <CompletenessBar value={column.completeness_pct} flag={column.quality_flag} />
            </TableCell>
            <TableCell className="text-xs">
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
            <TableCell
              className="max-w-[110px] truncate text-xs text-muted-foreground"
              title={formatScalar(column.min_value)}
            >
              {formatScalar(column.min_value)}
            </TableCell>
            <TableCell
              className="max-w-[110px] truncate text-xs text-muted-foreground"
              title={formatScalar(column.max_value)}
            >
              {formatScalar(column.max_value)}
            </TableCell>
            <TableCell className="text-xs">
              <Badge variant="outline">{column.inferred_logical_type}</Badge>
            </TableCell>
            <TableCell className="text-xs">
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
