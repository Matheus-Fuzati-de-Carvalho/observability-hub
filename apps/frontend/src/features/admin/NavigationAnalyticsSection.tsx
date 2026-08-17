import { Search } from 'lucide-react'
import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { PaginationBar } from '@/components/PaginationBar'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useNavigationAnalytics } from '@/features/admin/hooks'
import { usePagination } from '@/hooks/usePagination'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import type { SearchEntry, TableViewEntry } from '@/types/admin'

const TOP_LIMIT = 10

type GroupBy = 'project' | 'dataset' | 'table'

const GROUP_BY_LABELS: Record<GroupBy, string> = {
  project: 'Por projeto',
  dataset: 'Por dataset',
  table: 'Por tabela',
}

function groupKey(v: TableViewEntry, groupBy: GroupBy): string {
  if (groupBy === 'project') return v.project_id
  if (groupBy === 'dataset') return `${v.project_id}.${v.dataset_id}`
  return `${v.project_id}.${v.dataset_id}.${v.table_id}`
}

function topTableViews(
  views: TableViewEntry[],
  groupBy: GroupBy,
): { label: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const v of views) {
    const key = groupKey(v, groupBy)
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, TOP_LIMIT)
}

type FilterField = 'project' | 'dataset' | 'table'
type FilterOperator = 'contains' | 'not_contains' | 'is'

const FILTER_FIELD_LABELS: Record<FilterField, string> = {
  project: 'Projeto',
  dataset: 'Dataset',
  table: 'Tabela',
}

const FILTER_OPERATOR_LABELS: Record<FilterOperator, string> = {
  contains: 'Contém',
  not_contains: 'Não contém',
  is: 'É',
}

function fieldValue(v: TableViewEntry, field: FilterField): string {
  if (field === 'project') return v.project_id
  if (field === 'dataset') return v.dataset_id
  return v.table_id
}

function matchesFilter(
  v: TableViewEntry,
  field: FilterField,
  operator: FilterOperator,
  value: string,
): boolean {
  const needle = value.trim().toLowerCase()
  if (!needle) return true
  const haystack = fieldValue(v, field).toLowerCase()
  if (operator === 'contains') return haystack.includes(needle)
  if (operator === 'not_contains') return !haystack.includes(needle)
  return haystack === needle
}

interface SearchRow {
  project_id: string
  query: string
  count: number
}

function topSearches(searches: SearchEntry[]): SearchRow[] {
  const counts = new Map<string, SearchRow>()
  for (const s of searches) {
    const query = s.query.trim().toLowerCase()
    if (!query) continue
    const key = `${s.project_id}__${query}`
    const existing = counts.get(key)
    if (existing) {
      existing.count += 1
    } else {
      counts.set(key, { project_id: s.project_id, query, count: 1 })
    }
  }
  return [...counts.values()].sort((a, b) => b.count - a.count)
}

type SearchSortKey = 'project' | 'query' | 'count'

function compareSearchRows(a: SearchRow, b: SearchRow, key: SearchSortKey): number {
  if (key === 'project') return a.project_id.localeCompare(b.project_id)
  if (key === 'query') return a.query.localeCompare(b.query)
  return a.count - b.count
}

export function NavigationAnalyticsSection() {
  const navigationQuery = useNavigationAnalytics()

  const [groupBy, setGroupBy] = useState<GroupBy>('table')
  const [filterField, setFilterField] = useState<FilterField>('project')
  const [filterOperator, setFilterOperator] = useState<FilterOperator>('contains')
  const [filterValue, setFilterValue] = useState('')

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleSearches,
  } = useTableFilterSort<SearchRow, SearchSortKey>({
    rows: topSearches(navigationQuery.data?.searches ?? []),
    initialSortKey: 'count',
    compare: compareSearchRows,
    matches: (row, term) => {
      const t = term.toLowerCase()
      return row.project_id.toLowerCase().includes(t) || row.query.toLowerCase().includes(t)
    },
  })

  const searchesPagination = usePagination({ rowCount: visibleSearches.length })
  const pageSearches = visibleSearches.slice(searchesPagination.start, searchesPagination.end)

  if (navigationQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando navegação…</p>
  }

  if (navigationQuery.isError || !navigationQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar a navegação.</p>
  }

  const filteredViews = navigationQuery.data.table_views.filter((v) =>
    matchesFilter(v, filterField, filterOperator, filterValue),
  )
  const tables = topTableViews(filteredViews, groupBy)

  return (
    <CollapsibleSection title="Navegação">
      <p className="text-sm text-muted-foreground">
        Baseado nos últimos 20 itens de histórico por usuário — reflete uso recente, não o total
        histórico.
      </p>

      <CollapsibleSection
        title="Tabelas mais vistas"
        variant="subsection"
        actions={
          <div className="flex gap-1">
            {(Object.keys(GROUP_BY_LABELS) as GroupBy[]).map((option) => (
              <Button
                key={option}
                size="sm"
                variant={groupBy === option ? 'default' : 'outline'}
                onClick={() => setGroupBy(option)}
              >
                {GROUP_BY_LABELS[option]}
              </Button>
            ))}
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={filterField}
            onValueChange={(value) => setFilterField(value as FilterField)}
          >
            <SelectTrigger className="w-32">
              <SelectValue>{() => FILTER_FIELD_LABELS[filterField]}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="project">Projeto</SelectItem>
              <SelectItem value="dataset">Dataset</SelectItem>
              <SelectItem value="table">Tabela</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filterOperator}
            onValueChange={(value) => setFilterOperator(value as FilterOperator)}
          >
            <SelectTrigger className="w-36">
              <SelectValue>{() => FILTER_OPERATOR_LABELS[filterOperator]}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="contains">Contém</SelectItem>
              <SelectItem value="not_contains">Não contém</SelectItem>
              <SelectItem value="is">É</SelectItem>
            </SelectContent>
          </Select>
          <div className="relative min-w-[200px] flex-1">
            <Search
              size={14}
              className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
            />
            <Input
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
              placeholder={`Filtrar por ${FILTER_FIELD_LABELS[filterField].toLowerCase()}…`}
              className="pl-8"
            />
          </div>
        </div>

        {tables.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma visualização encontrada.</p>
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
      </CollapsibleSection>

      <CollapsibleSection title="Buscas mais frequentes" variant="subsection">
        <div className="relative max-w-sm">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por projeto ou busca…"
            className="pl-8"
          />
        </div>

        <div className="max-h-[420px] overflow-y-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableTableHead
                  label="Projeto"
                  active={sortKey === 'project'}
                  direction={sortDir}
                  onClick={() => toggleSort('project')}
                />
                <SortableTableHead
                  label="Busca"
                  active={sortKey === 'query'}
                  direction={sortDir}
                  onClick={() => toggleSort('query')}
                />
                <SortableTableHead
                  label="Ocorrências"
                  active={sortKey === 'count'}
                  direction={sortDir}
                  onClick={() => toggleSort('count')}
                  align="right"
                />
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageSearches.map((row) => (
                <TableRow key={`${row.project_id}__${row.query}`}>
                  <TableCell>{row.project_id}</TableCell>
                  <TableCell>{row.query}</TableCell>
                  <TableCell className="text-right">{row.count}</TableCell>
                </TableRow>
              ))}
              {visibleSearches.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-muted-foreground">
                    Nenhuma busca registrada ainda.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
        <PaginationBar
          page={searchesPagination.page}
          pageCount={searchesPagination.pageCount}
          pageSize={searchesPagination.pageSize}
          setPageSize={searchesPagination.setPageSize}
          start={searchesPagination.start}
          end={searchesPagination.end}
          totalCount={visibleSearches.length}
          onPrevious={searchesPagination.goToPreviousPage}
          onNext={searchesPagination.goToNextPage}
        />
      </CollapsibleSection>
    </CollapsibleSection>
  )
}
