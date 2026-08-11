import { Clock } from 'lucide-react'
import { Fragment } from 'react'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { ColumnDetail } from '@/types/catalog'

const DATE_TYPES = new Set(['DATE', 'DATETIME', 'TIMESTAMP'])
const SKELETON_ROW_IDS = ['s1', 's2', 's3', 's4', 's5']

interface StructField {
  name: string
  type: string
}

function isComplexType(dataType: string): boolean {
  const upper = dataType.toUpperCase()
  return upper.startsWith('ARRAY<') || upper.startsWith('STRUCT<')
}

function isDateType(dataType: string): boolean {
  return DATE_TYPES.has(dataType.toUpperCase())
}

// BigQuery representa STRUCT como texto literal, ex.
// "STRUCT<address STRUCT<city STRING>, tags ARRAY<STRING>>" — sem endpoint
// dedicado pra listar subcampos (a spec não pede mudança de backend), então
// o parsing é manual: acha o primeiro STRUCT<...> balanceado (profundidade
// de <>) e divide os campos por vírgula no nível 0.
function parseStructFields(dataType: string): StructField[] {
  const structStart = dataType.indexOf('STRUCT<')
  if (structStart === -1) return []

  const innerStart = structStart + 'STRUCT<'.length
  let depth = 1
  let end = innerStart
  for (; end < dataType.length && depth > 0; end++) {
    if (dataType[end] === '<') depth++
    else if (dataType[end] === '>') depth--
  }
  const inner = dataType.slice(innerStart, end - 1)

  const rawFields: string[] = []
  let fieldDepth = 0
  let current = ''
  for (const char of inner) {
    if (char === '<') fieldDepth++
    if (char === '>') fieldDepth--
    if (char === ',' && fieldDepth === 0) {
      rawFields.push(current.trim())
      current = ''
    } else {
      current += char
    }
  }
  if (current.trim()) rawFields.push(current.trim())

  return rawFields.map((field) => {
    const spaceIndex = field.indexOf(' ')
    return spaceIndex === -1
      ? { name: field, type: '' }
      : { name: field.slice(0, spaceIndex), type: field.slice(spaceIndex + 1).trim() }
  })
}

interface SchemaTableProps {
  columns: ColumnDetail[]
  isLoading: boolean
  partitionColumn: string | null
}

export function SchemaTable({ columns, isLoading, partitionColumn }: SchemaTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-xs">Nome</TableHead>
          <TableHead className="text-xs">Tipo</TableHead>
          <TableHead className="text-xs">Nullable</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading
          ? SKELETON_ROW_IDS.map((id) => (
              <TableRow key={id}>
                <TableCell>
                  <Skeleton className="h-4 w-32" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-24" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-10" />
                </TableCell>
              </TableRow>
            ))
          : columns.map((column) => {
              const complex = isComplexType(column.data_type)
              const dateColumn = isDateType(column.data_type)
              const isPartition = column.column_name === partitionColumn
              const subfields = complex ? parseStructFields(column.data_type) : []

              return (
                <Fragment key={column.column_name}>
                  <TableRow>
                    <TableCell
                      className={cn('text-xs font-medium', dateColumn && 'text-status-info')}
                    >
                      <span className="flex items-center gap-2">
                        {dateColumn && <Clock size={12} className="shrink-0" />}
                        {column.column_name}
                        {isPartition && <Badge>Partição</Badge>}
                      </span>
                    </TableCell>
                    <TableCell
                      className={cn(
                        'text-xs',
                        dateColumn ? 'text-status-info' : 'text-muted-foreground',
                      )}
                    >
                      <span className="flex items-center gap-2">
                        {column.data_type}
                        {complex && <Badge variant="outline">Complexo</Badge>}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {column.is_nullable ? 'Sim' : 'Não'}
                    </TableCell>
                  </TableRow>
                  {subfields.map((field) => (
                    <TableRow key={`${column.column_name}.${field.name}`}>
                      <TableCell className="pl-8 text-xs text-muted-foreground">
                        {field.name}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{field.type}</TableCell>
                      <TableCell />
                    </TableRow>
                  ))}
                </Fragment>
              )
            })}
      </TableBody>
    </Table>
  )
}
