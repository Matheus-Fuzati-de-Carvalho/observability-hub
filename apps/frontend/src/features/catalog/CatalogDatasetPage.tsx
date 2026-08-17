import { Star } from 'lucide-react'
import { useLocation, useParams } from 'react-router-dom'
import { RefreshButton } from '@/components/RefreshButton'
import { AssetsTable } from '@/features/catalog/AssetsTable'
import { useDatasets, useTables } from '@/features/catalog/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { isFavoriteDataset, useFavorites, useToggleFavorite } from '@/features/favorites/hooks'
import { useProjectFreshness } from '@/features/freshness/hooks'
import { SLA_LABELS } from '@/features/freshness/sla'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatNumber } from '@/lib/format'

export function CatalogDatasetPage() {
  const { projectId } = useProjectContext()
  const { datasetId } = useParams<{ datasetId: string }>()
  const location = useLocation()
  const highlightTableId = (location.state as { highlightTable?: string } | null)?.highlightTable

  const tablesQuery = useTables(projectId, datasetId)
  const datasetsQuery = useDatasets(projectId)
  const freshnessQuery = useProjectFreshness(projectId)
  const favoritesQuery = useFavorites()
  const toggleFavorite = useToggleFavorite()

  if (tablesQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (tablesQuery.isError || !tablesQuery.data) {
    return <p className="text-status-error">Erro ao carregar as tabelas do dataset.</p>
  }

  const datasetSummary = datasetsQuery.data?.datasets.find((d) => d.dataset_id === datasetId)
  const worstStatus = freshnessQuery.data?.datasets.find(
    (d) => d.dataset_id === datasetId,
  )?.worst_status
  const isRefreshing =
    tablesQuery.isFetching || datasetsQuery.isFetching || freshnessQuery.isFetching
  const isDatasetFavorite = isFavoriteDataset(
    favoritesQuery.data,
    projectId as string,
    tablesQuery.data.dataset_id,
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{tablesQuery.data.dataset_id}</h1>
            <button
              type="button"
              onClick={() =>
                toggleFavorite.mutate({
                  projectId: projectId as string,
                  datasetId: tablesQuery.data.dataset_id,
                  tableId: null,
                  isFavorite: isDatasetFavorite,
                })
              }
              aria-label={isDatasetFavorite ? 'Remover dataset dos favoritos' : 'Favoritar dataset'}
              className="text-muted-foreground hover:text-primary"
            >
              <Star
                size={18}
                className={isDatasetFavorite ? 'fill-primary text-primary' : undefined}
              />
            </button>
          </div>
          <p className="text-sm text-muted-foreground">{tablesQuery.data.total_tables} ativos</p>
        </div>
        <RefreshButton
          isRefreshing={isRefreshing}
          onRefresh={() => {
            tablesQuery.refetch()
            datasetsQuery.refetch()
            freshnessQuery.refetch()
          }}
        />
      </div>

      <KpiCards
        items={[
          { label: 'Região', value: tablesQuery.data.location },
          { label: 'Tabelas', value: String(datasetSummary?.total_tables ?? 0) },
          { label: 'Views', value: String(datasetSummary?.total_views ?? 0) },
          { label: 'Tamanho', value: `${(datasetSummary?.total_size_gb ?? 0).toFixed(2)} GB` },
          { label: 'Linhas', value: formatNumber(datasetSummary?.total_rows ?? null) },
          {
            label: 'Freshness',
            value: worstStatus ? SLA_LABELS[worstStatus] : '—',
            alert: worstStatus === 'stale' || worstStatus === 'warning_7d_1m',
          },
        ]}
      />

      <AssetsTable
        projectId={projectId as string}
        datasetId={datasetId as string}
        tables={tablesQuery.data.tables}
        highlightTableId={highlightTableId}
      />
    </div>
  )
}
