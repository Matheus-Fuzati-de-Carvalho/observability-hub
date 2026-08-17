import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
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
import { useAccessRequestAnalytics } from '@/features/admin/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'

export function AccessRequestAnalyticsSection() {
  const analyticsQuery = useAccessRequestAnalytics()

  if (analyticsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando solicitações de acesso…</p>
  }

  if (analyticsQuery.isError || !analyticsQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar as solicitações de acesso.</p>
  }

  const { monthly, top_projects, approval_rate } = analyticsQuery.data
  const totalRequests = monthly.reduce((sum, m) => sum + m.total, 0)

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-semibold text-lg">Solicitações de acesso</h2>

      <KpiCards
        items={[
          { label: 'Total de pedidos', value: String(totalRequests) },
          {
            label: 'Taxa de aprovação',
            value: approval_rate === null ? '—' : `${approval_rate.toFixed(1)}%`,
          },
        ]}
      />

      <div className="h-56 w-full shrink-0 rounded-lg border border-border bg-card p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={monthly}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="period" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
            <RechartsTooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar
              dataKey="approved"
              name="Aprovados"
              stackId="status"
              fill="var(--color-status-ok)"
            />
            <Bar
              dataKey="denied"
              name="Negados"
              stackId="status"
              fill="var(--color-status-error)"
            />
            <Bar
              dataKey="pending"
              name="Pendentes"
              stackId="status"
              fill="var(--color-status-warn)"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div>
        <p className="mb-2 text-sm text-muted-foreground">Projetos mais pedidos</p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Projeto</TableHead>
              <TableHead className="text-right">Pedidos</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {top_projects.map((project) => (
              <TableRow key={project.project_id}>
                <TableCell>{project.project_id}</TableCell>
                <TableCell className="text-right">{project.request_count}</TableCell>
              </TableRow>
            ))}
            {top_projects.length === 0 && (
              <TableRow>
                <TableCell colSpan={2} className="text-muted-foreground">
                  Nenhuma solicitação registrada ainda.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
