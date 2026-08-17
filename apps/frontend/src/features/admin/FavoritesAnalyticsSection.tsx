import { ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { PaginationBar } from '@/components/PaginationBar'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useFavoritesAnalytics } from '@/features/admin/hooks'
import { usePagination } from '@/hooks/usePagination'
import { formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { FavoriteEntry } from '@/types/admin'

type View = 'user' | 'project' | 'dataset' | 'table'

function baseKey(f: FavoriteEntry): string {
  return `${f.project_id}__${f.dataset_id}__${f.table_id ?? ''}`
}

function baseLabel(f: FavoriteEntry): string {
  return f.table_id
    ? `${f.project_id} · ${f.dataset_id}.${f.table_id}`
    : `${f.project_id} · ${f.dataset_id} (dataset completo)`
}

// Rótulo do item dentro de um grupo já agrupado por `view` — mostra só a
// parte do caminho que o agrupamento não cobre (ex: em "Por projeto",
// omite o projeto e mostra dataset.tabela).
function itemLabel(f: FavoriteEntry, view: View): string {
  if (view === 'user') return baseLabel(f)
  if (view === 'project') {
    return f.table_id ? `${f.dataset_id}.${f.table_id}` : `${f.dataset_id} (dataset completo)`
  }
  if (view === 'dataset') {
    return f.table_id ? f.table_id : '(dataset completo)'
  }
  return f.owner_email
}

interface Group {
  key: string
  label: string
  items: FavoriteEntry[]
}

function groupByUser(favorites: FavoriteEntry[]): Group[] {
  const map = new Map<string, FavoriteEntry[]>()
  for (const f of favorites) {
    const list = map.get(f.owner_email) ?? []
    list.push(f)
    map.set(f.owner_email, list)
  }
  return [...map.entries()]
    .map(([email, items]) => ({ key: email, label: email, items }))
    .sort((a, b) => b.items.length - a.items.length)
}

function groupByProject(favorites: FavoriteEntry[]): Group[] {
  const map = new Map<string, FavoriteEntry[]>()
  for (const f of favorites) {
    const list = map.get(f.project_id) ?? []
    list.push(f)
    map.set(f.project_id, list)
  }
  return [...map.entries()]
    .map(([project_id, items]) => ({ key: project_id, label: project_id, items }))
    .sort((a, b) => b.items.length - a.items.length)
}

function groupByDataset(favorites: FavoriteEntry[]): Group[] {
  const map = new Map<string, Group>()
  for (const f of favorites) {
    const key = `${f.project_id}__${f.dataset_id}`
    const existing = map.get(key)
    if (existing) {
      existing.items.push(f)
    } else {
      map.set(key, { key, label: `${f.project_id} · ${f.dataset_id}`, items: [f] })
    }
  }
  return [...map.values()].sort((a, b) => b.items.length - a.items.length)
}

function groupByTable(favorites: FavoriteEntry[]): Group[] {
  const map = new Map<string, Group>()
  for (const f of favorites) {
    const key = baseKey(f)
    const existing = map.get(key)
    if (existing) {
      existing.items.push(f)
    } else {
      map.set(key, { key, label: baseLabel(f), items: [f] })
    }
  }
  return [...map.values()].sort((a, b) => b.items.length - a.items.length)
}

function groupByView(favorites: FavoriteEntry[], view: View): Group[] {
  if (view === 'user') return groupByUser(favorites)
  if (view === 'project') return groupByProject(favorites)
  if (view === 'dataset') return groupByDataset(favorites)
  return groupByTable(favorites)
}

export function FavoritesAnalyticsSection() {
  const [view, setView] = useState<View>('table')
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const favoritesQuery = useFavoritesAnalytics()

  const favorites = favoritesQuery.data?.favorites ?? []
  const topBases = groupByTable(favorites)
  const groups = groupByView(favorites, view)

  const basesPagination = usePagination({ rowCount: topBases.length })
  const pageBases = topBases.slice(basesPagination.start, basesPagination.end)

  const groupsPagination = usePagination({ rowCount: groups.length })
  const pageGroups = groups.slice(groupsPagination.start, groupsPagination.end)

  function selectView(next: View) {
    setView(next)
    setExpandedKey(null)
    groupsPagination.resetPage()
  }

  if (favoritesQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando favoritos…</p>
  }

  if (favoritesQuery.isError || !favoritesQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar os favoritos.</p>
  }

  return (
    <CollapsibleSection title="Favoritos">
      <CollapsibleSection title="Bases mais favoritadas" variant="subsection">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Base</TableHead>
              <TableHead className="text-right">Favoritos</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageBases.map((group) => (
              <TableRow key={group.key}>
                <TableCell>{group.label}</TableCell>
                <TableCell className="text-right">{group.items.length}</TableCell>
              </TableRow>
            ))}
            {topBases.length === 0 && (
              <TableRow>
                <TableCell colSpan={2} className="text-muted-foreground">
                  Nenhum favorito registrado ainda.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <PaginationBar
          page={basesPagination.page}
          pageCount={basesPagination.pageCount}
          pageSize={basesPagination.pageSize}
          setPageSize={basesPagination.setPageSize}
          start={basesPagination.start}
          end={basesPagination.end}
          totalCount={topBases.length}
          onPrevious={basesPagination.goToPreviousPage}
          onNext={basesPagination.goToNextPage}
        />
      </CollapsibleSection>

      <CollapsibleSection
        title="Drill-down"
        variant="subsection"
        actions={
          <div className="flex gap-1">
            <Button
              size="sm"
              variant={view === 'user' ? 'default' : 'outline'}
              onClick={() => selectView('user')}
            >
              Por usuário
            </Button>
            <Button
              size="sm"
              variant={view === 'project' ? 'default' : 'outline'}
              onClick={() => selectView('project')}
            >
              Por projeto
            </Button>
            <Button
              size="sm"
              variant={view === 'dataset' ? 'default' : 'outline'}
              onClick={() => selectView('dataset')}
            >
              Por dataset
            </Button>
            <Button
              size="sm"
              variant={view === 'table' ? 'default' : 'outline'}
              onClick={() => selectView('table')}
            >
              Por tabela
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-0.5 rounded-lg border border-border">
          {pageGroups.map((group) => {
            const isExpanded = expandedKey === group.key
            return (
              <Collapsible
                key={group.key}
                open={isExpanded}
                onOpenChange={(open) => setExpandedKey(open ? group.key : null)}
              >
                <CollapsibleTrigger
                  className={cn(
                    'flex w-full items-center justify-between gap-2 px-3 py-2 text-sm hover:bg-muted',
                  )}
                >
                  <span className="flex items-center gap-1.5 truncate">
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    {group.label}
                  </span>
                  <span className="shrink-0 text-muted-foreground">
                    {group.items.length} {group.items.length === 1 ? 'item' : 'itens'}
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent className="max-h-64 overflow-y-auto border-border border-t bg-muted/30 px-3 py-2">
                  <ul className="flex flex-col gap-1 text-sm">
                    {group.items.map((item) => (
                      <li
                        key={`${item.owner_email}-${baseKey(item)}`}
                        className="flex items-center justify-between gap-2 text-muted-foreground"
                      >
                        <span className="truncate">
                          {itemLabel(item, view)}
                          {item.nickname && (
                            <span className="ml-1.5 text-xs italic">"{item.nickname}"</span>
                          )}
                        </span>
                        <span className="shrink-0 text-xs">{formatDate(item.added_at)}</span>
                      </li>
                    ))}
                  </ul>
                </CollapsibleContent>
              </Collapsible>
            )
          })}
          {groups.length === 0 && (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              Nenhum favorito registrado ainda.
            </p>
          )}
        </div>
        <PaginationBar
          page={groupsPagination.page}
          pageCount={groupsPagination.pageCount}
          pageSize={groupsPagination.pageSize}
          setPageSize={groupsPagination.setPageSize}
          start={groupsPagination.start}
          end={groupsPagination.end}
          totalCount={groups.length}
          onPrevious={groupsPagination.goToPreviousPage}
          onNext={groupsPagination.goToNextPage}
        />
      </CollapsibleSection>
    </CollapsibleSection>
  )
}
