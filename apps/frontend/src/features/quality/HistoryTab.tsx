import { ChevronDown, ChevronRight, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useQualityHistory } from '@/features/quality/hooks'
import { formatDate, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { QualityFlag } from '@/types/profiling'
import type { ProfilingHistoryRun } from '@/types/quality'

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

// "cai mais de 10%" da spec — pontos percentuais de densidade, não queda
// relativa, consistente com overall_density já ser um valor 0-100 (pp).
const DEGRADATION_THRESHOLD_PP = 10

function shortDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' }).format(date)
}

interface HistoryTabProps {
  projectId: string
  datasetId: string
  tableId: string | null
}

export function HistoryTab({ projectId, datasetId, tableId }: HistoryTabProps) {
  const [expandedRun, setExpandedRun] = useState<number | null>(null)
  const historyQuery = useQualityHistory(projectId, datasetId, tableId ?? undefined)

  if (historyQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando histórico…</p>
  }

  if (historyQuery.isError) {
    return <p className="text-sm text-status-error">Erro ao carregar o histórico.</p>
  }

  const runs = historyQuery.data?.runs ?? []

  if (runs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nenhum profiling executado ainda para esta tabela.
      </p>
    )
  }

  // runs vem do backend mais recente primeiro (bom pra tabela); o gráfico
  // precisa de ordem cronológica.
  const chartData = [...runs].reverse().map((run) => ({
    date: shortDate(run.executed_at),
    density: run.overall_density,
  }))

  const [latest, previous] = runs
  const densityDrop = previous ? previous.overall_density - latest.overall_density : 0
  const showDegradationAlert = previous !== undefined && densityDrop > DEGRADATION_THRESHOLD_PP

  return (
    <div className="flex flex-col gap-4">
      {showDegradationAlert && (
        <div className="flex items-center gap-2 rounded-lg border border-status-error/30 bg-status-error/10 p-3 text-sm text-status-error">
          <TriangleAlert size={16} className="shrink-0" />
          Densidade caiu {densityDrop.toFixed(1)} pontos percentuais desde o run anterior (
          {formatPercent(previous.overall_density)} → {formatPercent(latest.overall_density)}).
        </div>
      )}

      <div className="h-48 w-full shrink-0 rounded-lg border border-border bg-card p-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={36} />
            <RechartsTooltip formatter={(value) => [`${Number(value).toFixed(1)}%`, 'Densidade']} />
            <Line
              type="monotone"
              dataKey="density"
              stroke="var(--color-primary)"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8" />
            <TableHead>Data</TableHead>
            <TableHead>Executado por</TableHead>
            <TableHead className="text-right">Densidade</TableHead>
            <TableHead className="text-right">Duplicatas</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run, index) => (
            <RunRow
              key={run.executed_at}
              run={run}
              isExpanded={expandedRun === index}
              onToggle={() => setExpandedRun((current) => (current === index ? null : index))}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function RunRow({
  run,
  isExpanded,
  onToggle,
}: {
  run: ProfilingHistoryRun
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <TableRow className="cursor-pointer" onClick={onToggle}>
        <TableCell>{isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</TableCell>
        <TableCell>{formatDate(run.executed_at)}</TableCell>
        <TableCell className="text-muted-foreground">{run.executed_by}</TableCell>
        <TableCell className="text-right">{formatPercent(run.overall_density)}</TableCell>
        <TableCell className="text-right">{formatPercent(run.estimated_duplicate_pct)}</TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={5} className="bg-muted/30 p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Coluna</TableHead>
                  <TableHead className="text-xs">Completude</TableHead>
                  <TableHead className="text-xs">Quality flag</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {run.columns.map((column) => (
                  <TableRow key={column.column_name}>
                    <TableCell className="text-xs font-medium">{column.column_name}</TableCell>
                    <TableCell className="text-xs">
                      {formatPercent(column.completeness_pct)}
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
          </TableCell>
        </TableRow>
      )}
    </>
  )
}
