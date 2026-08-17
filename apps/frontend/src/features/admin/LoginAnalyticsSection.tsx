import {
  CartesianGrid,
  Line,
  LineChart,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { PaginationBar } from '@/components/PaginationBar'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useLoginAnalytics } from '@/features/admin/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { usePagination } from '@/hooks/usePagination'
import { formatDate } from '@/lib/format'
import type { LoginCountBucket } from '@/types/admin'

const LOOKBACK_DAYS = 90

function todayDailyKey(): string {
  return new Date().toISOString().slice(0, 10)
}

// Mesmo algoritmo de datetime.isocalendar() do Python (ISO 8601) — precisa
// bater exatamente com o formato gerado no backend pra achar o bucket da
// semana atual.
function isoWeekKey(now: Date): string {
  const date = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()))
  const dayNum = (date.getUTCDay() + 6) % 7
  date.setUTCDate(date.getUTCDate() - dayNum + 3)
  const firstThursday = new Date(Date.UTC(date.getUTCFullYear(), 0, 4))
  const firstDayNum = (firstThursday.getUTCDay() + 6) % 7
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3)
  const week = 1 + Math.round((date.getTime() - firstThursday.getTime()) / (7 * 86400000))
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}

function monthKey(now: Date): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function shortDate(period: string): string {
  const date = new Date(period)
  if (Number.isNaN(date.getTime())) return period
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' }).format(date)
}

function findBucket(buckets: LoginCountBucket[], period: string): LoginCountBucket | undefined {
  return buckets.find((b) => b.period === period)
}

export function LoginAnalyticsSection() {
  const analyticsQuery = useLoginAnalytics(LOOKBACK_DAYS)

  const recentEvents = analyticsQuery.data?.recent_events ?? []
  const pagination = usePagination({ rowCount: recentEvents.length })
  const pageEvents = recentEvents.slice(pagination.start, pagination.end)

  if (analyticsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando acessos…</p>
  }

  if (analyticsQuery.isError || !analyticsQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar os acessos ao Hub.</p>
  }

  const { daily, weekly, monthly, recent_events } = analyticsQuery.data
  const now = new Date()
  const today = findBucket(daily, todayDailyKey())
  const thisWeek = findBucket(weekly, isoWeekKey(now))
  const thisMonth = findBucket(monthly, monthKey(now))

  const chartData = daily.map((bucket) => ({
    date: shortDate(bucket.period),
    logins: bucket.login_count,
  }))

  return (
    <CollapsibleSection title="Acessos ao Hub">
      <KpiCards
        items={[
          { label: 'Acessos hoje', value: String(today?.login_count ?? 0) },
          { label: 'Usuários únicos hoje', value: String(today?.unique_users ?? 0) },
          { label: 'Acessos esta semana', value: String(thisWeek?.login_count ?? 0) },
          { label: 'Acessos este mês', value: String(thisMonth?.login_count ?? 0) },
        ]}
      />

      <div className="h-48 w-full shrink-0 rounded-lg border border-border bg-card p-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
            <RechartsTooltip formatter={(value) => [String(value), 'Acessos']} />
            <Line
              type="monotone"
              dataKey="logins"
              stroke="var(--color-primary)"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <CollapsibleSection
        title={`Acessos recentes (últimos ${recent_events.length})`}
        variant="subsection"
      >
        <div className="max-h-[420px] overflow-y-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>E-mail</TableHead>
                <TableHead>Quando</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageEvents.map((event) => (
                <TableRow key={`${event.email}-${event.logged_in_at}`}>
                  <TableCell>{event.email}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(event.logged_in_at)}
                  </TableCell>
                </TableRow>
              ))}
              {recent_events.length === 0 && (
                <TableRow>
                  <TableCell colSpan={2} className="text-muted-foreground">
                    Nenhum acesso registrado ainda.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
        <PaginationBar
          page={pagination.page}
          pageCount={pagination.pageCount}
          pageSize={pagination.pageSize}
          setPageSize={pagination.setPageSize}
          start={pagination.start}
          end={pagination.end}
          totalCount={recent_events.length}
          onPrevious={pagination.goToPreviousPage}
          onNext={pagination.goToNextPage}
        />
      </CollapsibleSection>
    </CollapsibleSection>
  )
}
