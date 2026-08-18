import {
  ChevronDown,
  Clock,
  Database,
  DollarSign,
  HardDrive,
  History,
  PiggyBank,
  Search,
  Star,
  Unlink,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { useDatasets } from '@/features/catalog/hooks'
import { FavoriteNickname } from '@/features/favorites/FavoriteNickname'
import {
  isFavoriteDataset,
  useFavorites,
  useToggleFavorite,
  useUpdateFavoriteNickname,
} from '@/features/favorites/hooks'
import { useHistory } from '@/features/history/hooks'
import { cn } from '@/lib/utils'
import type { Favorite } from '@/types/favorites'

const MAX_RECENT_TABLES_SHOWN = 5

interface DatasetSidebarProps {
  projectId: string
}

const NAV_LINK_CLASS = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
    isActive ? 'bg-primary font-bold text-primary-foreground' : 'text-foreground hover:bg-muted',
  )

const SECTION_LABEL_CLASS =
  'px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase'

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

// Nó de topo de um serviço observável (hoje só BigQuery — o Hub existe pra
// expandir pra outros serviços GCP no futuro, cada um vira um
// SidebarServiceGroup irmão deste). Visualmente mais forte que
// SidebarSection (ícone, texto não-muted, sem uppercase) pra marcar a
// hierarquia: serviço > seção > item.
function SidebarServiceGroup({
  icon,
  label,
  open,
  onOpenChange,
  children,
}: {
  icon: ReactNode
  label: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      <CollapsibleTrigger className="mb-2 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm font-bold text-foreground transition-colors hover:bg-muted">
        {icon}
        <span className="flex-1 text-left">{label}</span>
        <ChevronDown size={14} className={cn('transition-transform', !open && '-rotate-90')} />
      </CollapsibleTrigger>
      <CollapsibleContent className="flex flex-col gap-3 border-border border-l pl-2">
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}

// Subseção dentro de um serviço (Governança, FinOps, Datasets
// disponíveis, Favoritos, Recentes) — todas recolhidas por padrão
// (`open` vem de fora, sempre iniciado em `false` no componente pai).
function SidebarSection({
  label,
  open,
  onOpenChange,
  children,
}: {
  label: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      <CollapsibleTrigger
        className={cn(SECTION_LABEL_CLASS, 'mb-2 flex w-full items-center justify-between')}
      >
        {label}
        <ChevronDown size={14} className={cn('transition-transform', !open && '-rotate-90')} />
      </CollapsibleTrigger>
      <CollapsibleContent>{children}</CollapsibleContent>
    </Collapsible>
  )
}

export function DatasetSidebar({ projectId }: DatasetSidebarProps) {
  const datasetsQuery = useDatasets(projectId)
  const favoritesQuery = useFavorites()
  const toggleFavorite = useToggleFavorite()
  const updateNickname = useUpdateFavoriteNickname()
  const projectFavorites = favoritesQuery.data?.favorites.filter((f) => f.project_id === projectId)
  const tableFavorites = projectFavorites?.filter(
    (f): f is Favorite & { table_id: string } => f.table_id !== null,
  )
  const datasetFavorites = projectFavorites?.filter((f) => f.table_id === null)
  const historyQuery = useHistory()
  const recentTables = historyQuery.data?.recent_tables
    .filter((t) => t.project_id === projectId)
    .slice(0, MAX_RECENT_TABLES_SHOWN)

  // BigQuery é o serviço com mais conteúdo hoje — abre por padrão (sidebar
  // vazia no primeiro acesso seria má UX). Cloud Storage começa recolhido,
  // mesmo padrão de subseção nova com pouco conteúdo ainda. Tudo que abre
  // DENTRO de um serviço começa recolhido, sem exceção.
  const [bigQueryOpen, setBigQueryOpen] = useState(true)
  const [cloudStorageOpen, setCloudStorageOpen] = useState(false)
  const [governanceOpen, setGovernanceOpen] = useState(false)
  const [finopsOpen, setFinopsOpen] = useState(false)
  const [datasetsOpen, setDatasetsOpen] = useState(false)
  const [favoritesOpen, setFavoritesOpen] = useState(false)
  const [recentOpen, setRecentOpen] = useState(false)
  const [datasetFilter, setDatasetFilter] = useState('')
  const visibleDatasets = datasetsQuery.data?.datasets.filter((dataset) =>
    dataset.dataset_id.toLowerCase().includes(datasetFilter.toLowerCase()),
  )

  return (
    <aside className="w-60 shrink-0 overflow-y-auto border-r border-border bg-card p-4">
      <SidebarServiceGroup
        icon={<Database size={16} />}
        label="BigQuery"
        open={bigQueryOpen}
        onOpenChange={setBigQueryOpen}
      >
        <SidebarSection label="Governança" open={governanceOpen} onOpenChange={setGovernanceOpen}>
          <nav className="flex flex-col gap-0.5">
            <NavLink to="/freshness" className={NAV_LINK_CLASS}>
              <Clock size={16} />
              Freshness
            </NavLink>
            <NavLink to="/orphans" className={NAV_LINK_CLASS}>
              <Unlink size={16} />
              Tabelas sem consumidor
            </NavLink>
          </nav>
        </SidebarSection>

        <SidebarSection label="FinOps" open={finopsOpen} onOpenChange={setFinopsOpen}>
          <nav className="flex flex-col gap-0.5">
            <NavLink to="/finops" end className={NAV_LINK_CLASS}>
              <PiggyBank size={16} />
              Scanner de desperdício
            </NavLink>
            <NavLink to="/finops/budget" className={NAV_LINK_CLASS}>
              <DollarSign size={16} />
              Budget de custo
            </NavLink>
          </nav>
        </SidebarSection>

        <SidebarSection
          label="Datasets disponíveis"
          open={datasetsOpen}
          onOpenChange={setDatasetsOpen}
        >
          <NavLink to="/search" className={NAV_LINK_CLASS}>
            <Search size={16} />
            Buscar tabelas
          </NavLink>

          {datasetsQuery.isLoading && (
            <p className="px-3 text-sm text-muted-foreground">Carregando…</p>
          )}

          {datasetsQuery.isError && (
            <p className="px-3 text-sm text-status-error">Erro ao carregar datasets.</p>
          )}

          {datasetsQuery.data && datasetsQuery.data.datasets.length > 0 && (
            <div className="relative mb-2 px-3">
              <Search
                size={13}
                className="-translate-y-1/2 absolute top-1/2 left-5.5 text-muted-foreground"
              />
              <Input
                value={datasetFilter}
                onChange={(e) => setDatasetFilter(e.target.value)}
                placeholder="Filtrar datasets…"
                className="h-8 pl-7 text-sm"
              />
            </div>
          )}

          <nav className="flex flex-col gap-0.5">
            {visibleDatasets?.map((dataset) => {
              const isDatasetFavorite = isFavoriteDataset(
                favoritesQuery.data,
                projectId,
                dataset.dataset_id,
              )
              return (
                <div key={dataset.dataset_id} className="flex items-center gap-1">
                  <NavLink
                    to={`/datasets/${dataset.dataset_id}`}
                    className={({ isActive }) =>
                      cn(
                        'flex min-w-0 flex-1 items-center justify-between rounded-md px-3 py-2 text-sm transition-colors',
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
                  <button
                    type="button"
                    onClick={() =>
                      toggleFavorite.mutate({
                        projectId,
                        datasetId: dataset.dataset_id,
                        tableId: null,
                        isFavorite: isDatasetFavorite,
                      })
                    }
                    aria-label={
                      isDatasetFavorite ? 'Remover dataset dos favoritos' : 'Favoritar dataset'
                    }
                    className="shrink-0 px-1 text-muted-foreground hover:text-primary"
                  >
                    <Star
                      size={13}
                      className={isDatasetFavorite ? 'fill-primary text-primary' : undefined}
                    />
                  </button>
                </div>
              )
            })}
            {visibleDatasets && visibleDatasets.length === 0 && (
              <p className="px-3 text-sm text-muted-foreground">Nenhum dataset encontrado.</p>
            )}
          </nav>
        </SidebarSection>

        {projectFavorites && projectFavorites.length > 0 && (
          <SidebarSection label="Favoritos" open={favoritesOpen} onOpenChange={setFavoritesOpen}>
            <div className="flex flex-col gap-3">
              {tableFavorites && tableFavorites.length > 0 && (
                <div>
                  <p className="px-3 text-[11px] font-semibold tracking-wide text-muted-foreground/70 uppercase">
                    Tabelas favoritas
                  </p>
                  <nav className="flex flex-col gap-0.5">
                    {tableFavorites.map((favorite) => (
                      <div
                        key={`${favorite.dataset_id}.${favorite.table_id}`}
                        className="group flex flex-col gap-0.5 rounded-md px-3 py-2 transition-colors hover:bg-muted"
                      >
                        <Link
                          to={`/datasets/${favorite.dataset_id}`}
                          state={{ highlightTable: favorite.table_id }}
                          className="flex items-center gap-2 text-sm text-foreground"
                        >
                          <Star size={12} className="shrink-0 fill-primary text-primary" />
                          <span className="truncate">
                            {favorite.dataset_id}.{favorite.table_id}
                          </span>
                        </Link>
                        <FavoriteNickname
                          nickname={favorite.nickname}
                          onSave={(nickname) =>
                            updateNickname.mutate({
                              projectId,
                              datasetId: favorite.dataset_id,
                              tableId: favorite.table_id,
                              nickname,
                            })
                          }
                        />
                      </div>
                    ))}
                  </nav>
                </div>
              )}

              {datasetFavorites && datasetFavorites.length > 0 && (
                <div>
                  <p className="px-3 text-[11px] font-semibold tracking-wide text-muted-foreground/70 uppercase">
                    Datasets favoritos
                  </p>
                  <nav className="flex flex-col gap-0.5">
                    {datasetFavorites.map((favorite) => (
                      <div
                        key={favorite.dataset_id}
                        className="group flex flex-col gap-0.5 rounded-md px-3 py-2 transition-colors hover:bg-muted"
                      >
                        <Link
                          to={`/datasets/${favorite.dataset_id}`}
                          className="flex items-center gap-2 text-sm text-foreground"
                        >
                          <Star size={12} className="shrink-0 fill-primary text-primary" />
                          <span className="truncate">{favorite.dataset_id}</span>
                        </Link>
                        <FavoriteNickname
                          nickname={favorite.nickname}
                          onSave={(nickname) =>
                            updateNickname.mutate({
                              projectId,
                              datasetId: favorite.dataset_id,
                              tableId: null,
                              nickname,
                            })
                          }
                        />
                      </div>
                    ))}
                  </nav>
                </div>
              )}
            </div>
          </SidebarSection>
        )}

        {recentTables && recentTables.length > 0 && (
          <SidebarSection label="Recentes" open={recentOpen} onOpenChange={setRecentOpen}>
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
          </SidebarSection>
        )}
      </SidebarServiceGroup>

      <SidebarServiceGroup
        icon={<HardDrive size={16} />}
        label="Cloud Storage"
        open={cloudStorageOpen}
        onOpenChange={setCloudStorageOpen}
      >
        <nav className="flex flex-col gap-0.5">
          <NavLink to="/storage" end className={NAV_LINK_CLASS}>
            <HardDrive size={16} />
            Buckets
          </NavLink>
          <NavLink to="/storage/waste" className={NAV_LINK_CLASS}>
            <PiggyBank size={16} />
            Scanner de desperdício
          </NavLink>
        </nav>
      </SidebarServiceGroup>
    </aside>
  )
}
