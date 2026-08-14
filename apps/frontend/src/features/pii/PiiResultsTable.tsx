import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { PiiColumnResult, PiiType } from '@/types/pii'

const PII_TYPE_LABELS: Record<PiiType, string> = {
  email: 'Email',
  cpf: 'CPF',
  cnpj: 'CNPJ',
  telefone_br: 'Telefone',
  cep: 'CEP',
  cartao_credito: 'Cartão de crédito',
}

const CONFIDENCE_LABELS: Record<'high' | 'medium', string> = {
  high: 'Alta',
  medium: 'Média',
}

const CONFIDENCE_COLOR: Record<'high' | 'medium', string> = {
  high: 'text-status-error',
  medium: 'text-status-warn',
}

export function PiiResultsTable({ columns }: { columns: PiiColumnResult[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-xs">Coluna</TableHead>
          <TableHead className="text-xs">Tipo</TableHead>
          <TableHead className="text-xs">Heurística de nome</TableHead>
          <TableHead className="text-xs">Amostra</TableHead>
          <TableHead className="text-xs">Confiança</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {columns.map((column) => (
          <TableRow key={column.column_name} className={cn(column.flagged && 'bg-status-warn/5')}>
            <TableCell className="text-xs font-medium">{column.column_name}</TableCell>
            <TableCell className="text-xs text-muted-foreground">{column.data_type}</TableCell>
            <TableCell className="text-xs">
              {column.name_match_types.length === 0 ? (
                <span className="text-muted-foreground">—</span>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {column.name_match_types.map((type) => (
                    <Badge key={type} variant="outline">
                      {PII_TYPE_LABELS[type]}
                    </Badge>
                  ))}
                </div>
              )}
            </TableCell>
            <TableCell className="text-xs">
              {column.sample_non_null_count === null ? (
                <span className="text-muted-foreground">Não amostrada</span>
              ) : column.sample_matches.length === 0 ? (
                <span className="text-muted-foreground">Sem match</span>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {column.sample_matches.map((match) => (
                    <Badge
                      key={match.pii_type}
                      variant={match.flagged ? 'default' : 'outline'}
                      title={`${match.match_count} de ${column.sample_non_null_count} valores amostrados`}
                    >
                      {PII_TYPE_LABELS[match.pii_type]} {(match.match_ratio * 100).toFixed(1)}%
                    </Badge>
                  ))}
                </div>
              )}
            </TableCell>
            <TableCell className="text-xs">
              {column.confidence ? (
                <span className={cn('font-medium', CONFIDENCE_COLOR[column.confidence])}>
                  {CONFIDENCE_LABELS[column.confidence]}
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
