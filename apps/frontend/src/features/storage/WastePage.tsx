import { useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useWasteCandidates } from '@/features/storage/hooks'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatNumber } from '@/lib/format'
import type { MinDaysUnused, WasteCandidate } from '@/types/storage'

const MIN_DAYS_OPTIONS: MinDaysUnused[] = [30, 60, 90]

type SortKey =
  | 'bucket_name'
  | 'eligible_object_count'
  | 'eligible_size_bytes'
  | 'oldest_object_age_days'
  | 'estimated_savings_usd_month_min'
  | 'confidence'

function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

function compare(a: WasteCandidate, b: WasteCandidate, key: SortKey): number {
  if (key === 'bucket_name') {
    return a.bucket_name.localeCompare(b.bucket_name)
  }
  if (key === 'confidence') {
    return a.confidence.localeCompare(b.confidence)
  }
  return a[key] - b[key]
}

function ConfidenceBadge({ candidate }: { candidate: WasteCandidate }) {
  if (candidate.confidence === 'usage_confirmed') {
    return (
      <Badge
        variant="secondary"
        className="border-status-ok/30 bg-status-ok/10 text-status-ok"
        title={`${candidate.usage_confirmed_object_count} de ${candidate.eligible_object_count} objetos sem leitura registrada nos últimos 90 dias`}
      >
        Sem leitura confirmada
      </Badge>
    )
  }
  return (
    <Badge
      variant="secondary"
      title={
        candidate.usage_confirmed_object_count > 0
          ? `${candidate.usage_confirmed_object_count} de ${candidate.eligible_object_count} objetos sem leitura registrada — os demais foram lidos nos últimos 90 dias`
          : 'Baseado só em idade + ausência de lifecycle rule, sem checagem de leitura'
      }
    >
      Só configuração
    </Badge>
  )
}

export function WastePage() {
  const { projectId } = useProjectContext()
  const [minDaysUnused, setMinDaysUnused] = useState<MinDaysUnused>(60)
  const wasteQuery = useWasteCandidates(projectId, minDaysUnused)
  const data = wasteQuery.data

  const {
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleCandidates,
  } = useTableFilterSort<WasteCandidate, SortKey>({
    rows: data?.candidates ?? [],
    initialSortKey: 'estimated_savings_usd_month_min',
    compare,
    matches: () => true,
  })

  if (wasteQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (wasteQuery.isError) {
    return <ApiErrorNotice error={wasteQuery.error} />
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Scanner de desperdício</h1>
          <p className="text-sm text-muted-foreground">
            {data.candidates.length} buckets candidatos a mudança de storage class
          </p>
        </div>
        <RefreshButton
          isRefreshing={wasteQuery.isFetching}
          onRefresh={() => wasteQuery.refetch()}
        />
      </div>

      {data.usage_check_warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.usage_check_warning}
        </div>
      )}

      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">
          Objetos STANDARD sem modificação há pelo menos
        </span>
        <Select
          value={String(minDaysUnused)}
          onValueChange={(value) => setMinDaysUnused(Number(value) as MinDaysUnused)}
        >
          <SelectTrigger className="w-24">
            <SelectValue>{(value: string) => `${value} dias`}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {MIN_DAYS_OPTIONS.map((days) => (
              <SelectItem key={days} value={String(days)}>
                {days} dias
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Bucket"
              active={sortKey === 'bucket_name'}
              direction={sortDir}
              onClick={() => toggleSort('bucket_name')}
            />
            <SortableTableHead
              label="Objetos elegíveis"
              active={sortKey === 'eligible_object_count'}
              direction={sortDir}
              onClick={() => toggleSort('eligible_object_count')}
              align="right"
            />
            <SortableTableHead
              label="Tamanho"
              active={sortKey === 'eligible_size_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('eligible_size_bytes')}
              align="right"
            />
            <SortableTableHead
              label="Objeto mais antigo"
              active={sortKey === 'oldest_object_age_days'}
              direction={sortDir}
              onClick={() => toggleSort('oldest_object_age_days')}
              align="right"
            />
            <SortableTableHead
              label="Economia estimada/mês"
              active={sortKey === 'estimated_savings_usd_month_min'}
              direction={sortDir}
              onClick={() => toggleSort('estimated_savings_usd_month_min')}
              align="right"
            />
            <SortableTableHead
              label="Confiança"
              active={sortKey === 'confidence'}
              direction={sortDir}
              onClick={() => toggleSort('confidence')}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleCandidates.map((candidate) => (
            <TableRow key={candidate.bucket_name}>
              <TableCell className="font-medium">{candidate.bucket_name}</TableCell>
              <TableCell className="text-right">
                {formatNumber(candidate.eligible_object_count)}
              </TableCell>
              <TableCell className="text-right">
                {formatBytes(candidate.eligible_size_bytes)}
              </TableCell>
              <TableCell className="text-right">{candidate.oldest_object_age_days} dias</TableCell>
              <TableCell className="text-right" title={data.savings_disclaimer}>
                {formatUsd(candidate.estimated_savings_usd_month_min)} –{' '}
                {formatUsd(candidate.estimated_savings_usd_month_max)}
              </TableCell>
              <TableCell>
                <ConfidenceBadge candidate={candidate} />
              </TableCell>
            </TableRow>
          ))}
          {visibleCandidates.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground">
                Nenhum bucket candidato encontrado com esse threshold.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
