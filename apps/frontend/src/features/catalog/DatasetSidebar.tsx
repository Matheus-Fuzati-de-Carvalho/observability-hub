import { Clock, History, Search, Star } from 'lucide-react'
import { Link, NavLink } from 'react-router-dom'
import { useDatasets } from '@/features/catalog/hooks'
import { useFavorites } from '@/features/favorites/hooks'
import { useHistory } from '@/features/history/hooks'
import { cn } from '@/lib/utils'

const MAX_RECENT_TABLES_SHOWN = 5

interface DatasetSidebarProps {
  projectId: string
}

// Só mostra "· views" quando há tabelas e views ao mesmo tempo — dataset só
// de views (ou só de tabelas) mostra um único número, sem "0 tabelas"/"0
// views" ao lado.
function formatAssetCounts(totalTables: number, totalViews: number): string {
  const tablesLabel = `${totalTables} ${totalTables === 1 ? 'tabela' : 'tabelas'}`
  const viewsLabel = `${totalViews} ${totalViews === 1 ? 'view' : 'views'}`
  if (totalTables > 0 && totalViews > 0) return `${tablesLabel} · ${viewsLabel}`
  if (totalTables === 0 && totalViews > 0) return viewsLabel
  return tablesLabel
}

export function DatasetSidebar({ projectId }: DatasetSidebarProps) {
  const datasetsQuery = useDatasets(projectId)
  const favoritesQuery = useFavorites()
  const projectFavorites = favoritesQuery.data?.favorites.filter((f) => f.project_id === projectId)
  const historyQuery = useHistory()
  const recentTables = historyQuery.data?.recent_tables
    .filter((t) => t.project_id === projectId)
    .slice(0, MAX_RECENT_TABLES_SHOWN)

  return (
    <aside className="w-60 shrink-0 border-r border-border bg-card p-4">
      <div className="mb-4 flex flex-col gap-0.5">
        <NavLink
          to="/freshness"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
              isActive
                ? 'bg-primary font-bold text-primary-foreground'
                : 'text-foreground hover:bg-muted',
            )
          }
        >
          <Clock size={16} />
          Freshness
        </NavLink>
        <NavLink
          to="/search"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
              isActive
                ? 'bg-primary font-bold text-primary-foreground'
                : 'text-foreground hover:bg-muted',
            )
          }
        >
          <Search size={16} />
          Busca
        </NavLink>
      </div>

      <p className="mb-2 px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        Datasets disponíveis
      </p>

      {datasetsQuery.isLoading && <p className="px-3 text-sm text-muted-foreground">Carregando…</p>}

      {datasetsQuery.isError && (
        <p className="px-3 text-sm text-status-error">Erro ao carregar datasets.</p>
      )}

      <nav className="flex flex-col gap-0.5">
        {datasetsQuery.data?.datasets.map((dataset) => (
          <NavLink
            key={dataset.dataset_id}
            to={`/datasets/${dataset.dataset_id}`}
            className={({ isActive }) =>
              cn(
                'flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-primary font-bold text-primary-foreground'
                  : 'text-foreground hover:bg-muted',
              )
            }
          >
            <span className="truncate">{dataset.dataset_id}</span>
            <span className="shrink-0 text-xs opacity-70">
              [{formatAssetCounts(dataset.total_tables, dataset.total_views)}]
            </span>
          </NavLink>
        ))}
      </nav>

      {projectFavorites && projectFavorites.length > 0 && (
        <>
          <p className="mt-4 mb-2 px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Favoritos
          </p>
          <nav className="flex flex-col gap-0.5">
            {projectFavorites.map((favorite) => (
              <Link
                key={`${favorite.dataset_id}.${favorite.table_id}`}
                to={`/datasets/${favorite.dataset_id}`}
                state={{ highlightTable: favorite.table_id }}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
              >
                <Star size={12} className="shrink-0 fill-primary text-primary" />
                <span className="truncate">
                  {favorite.dataset_id}.{favorite.table_id}
                </span>
              </Link>
            ))}
          </nav>
        </>
      )}

      {recentTables && recentTables.length > 0 && (
        <>
          <p className="mt-4 mb-2 px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Recentes
          </p>
          <nav className="flex flex-col gap-0.5">
            {recentTables.map((view) => (
              <Link
                key={`${view.dataset_id}.${view.table_id}.${view.viewed_at}`}
                to={`/datasets/${view.dataset_id}`}
                state={{ highlightTable: view.table_id }}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
              >
                <History size={12} className="shrink-0 text-muted-foreground" />
                <span className="truncate">
                  {view.dataset_id}.{view.table_id}
                </span>
              </Link>
            ))}
          </nav>
        </>
      )}
    </aside>
  )
}
