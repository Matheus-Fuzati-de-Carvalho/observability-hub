import { Clock, Search } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useDatasets } from '@/features/catalog/hooks'
import { cn } from '@/lib/utils'

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
    </aside>
  )
}
