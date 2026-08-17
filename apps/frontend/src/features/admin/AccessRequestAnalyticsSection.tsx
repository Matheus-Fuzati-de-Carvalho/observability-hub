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
import { useAccessRequestAnalytics } from '@/features/admin/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { usePagination } from '@/hooks/usePagination'

export function AccessRequestAnalyticsSection() {
  const analyticsQuery = useAccessRequestAnalytics()

  const topProjects = analyticsQuery.data?.top_projects ?? []
  const pagination = usePagination({ rowCount: topProjects.length })
  const pageProjects = topProjects.slice(pagination.start, pagination.end)

  if (analyticsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando solicitações de acesso…</p>
  }

  if (analyticsQuery.isError || !analyticsQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar as solicitações de acesso.</p>
  }

  const { monthly, top_projects, approval_rate } = analyticsQuery.data
  const totalRequests = monthly.reduce((sum, m) => sum + m.total, 0)

  return (
    <CollapsibleSection title="Solicitações de acesso">
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

      <CollapsibleSection title="Projetos mais pedidos" variant="subsection">
        <div className="max-h-[420px] overflow-y-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Projeto</TableHead>
                <TableHead className="text-right">Pedidos</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageProjects.map((project) => (
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
        <PaginationBar
          page={pagination.page}
          pageCount={pagination.pageCount}
          pageSize={pagination.pageSize}
          setPageSize={pagination.setPageSize}
          start={pagination.start}
          end={pagination.end}
          totalCount={top_projects.length}
          onPrevious={pagination.goToPreviousPage}
          onNext={pagination.goToNextPage}
        />
      </CollapsibleSection>
    </CollapsibleSection>
  )
}
