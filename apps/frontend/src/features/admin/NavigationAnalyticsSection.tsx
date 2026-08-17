import {
  Bar,
  BarChart,
  CartesianGrid,
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
import { useNavigationAnalytics } from '@/features/admin/hooks'
import type { SearchEntry, TableViewEntry } from '@/types/admin'

const TOP_LIMIT = 10

function topTableViews(views: TableViewEntry[]): { label: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const v of views) {
    const key = `${v.project_id}.${v.dataset_id}.${v.table_id}`
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, TOP_LIMIT)
}

function topSearches(searches: SearchEntry[]): { query: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const s of searches) {
    const key = s.query.trim().toLowerCase()
    if (!key) continue
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([query, count]) => ({ query, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, TOP_LIMIT)
}

export function NavigationAnalyticsSection() {
  const navigationQuery = useNavigationAnalytics()

  if (navigationQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando navegação…</p>
  }

  if (navigationQuery.isError || !navigationQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar a navegação.</p>
  }

  const tables = topTableViews(navigationQuery.data.table_views)
  const searches = topSearches(navigationQuery.data.searches)

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-semibold text-lg">Navegação</h2>
        <p className="text-sm text-muted-foreground">
          Baseado nos últimos 20 itens de histórico por usuário — reflete uso recente, não o total
          histórico.
        </p>
      </div>

      <div>
        <p className="mb-2 text-sm text-muted-foreground">Tabelas mais vistas</p>
        {tables.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma visualização registrada ainda.</p>
        ) : (
          <div
            className="w-full rounded-lg border border-border bg-card p-4"
            style={{ height: Math.max(tables.length * 32, 120) }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tables} layout="vertical" margin={{ left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="label"
                  tick={{ fontSize: 11 }}
                  width={220}
                  interval={0}
                />
                <RechartsTooltip formatter={(value) => [String(value), 'Visualizações']} />
                <Bar dataKey="count" fill="var(--color-primary)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-sm text-muted-foreground">Buscas mais frequentes</p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Busca</TableHead>
              <TableHead className="text-right">Ocorrências</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {searches.map((search) => (
              <TableRow key={search.query}>
                <TableCell>{search.query}</TableCell>
                <TableCell className="text-right">{search.count}</TableCell>
              </TableRow>
            ))}
            {searches.length === 0 && (
              <TableRow>
                <TableCell colSpan={2} className="text-muted-foreground">
                  Nenhuma busca registrada ainda.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
