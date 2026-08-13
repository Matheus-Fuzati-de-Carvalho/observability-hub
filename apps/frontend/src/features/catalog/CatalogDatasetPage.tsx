import { useEffect, useRef } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { RefreshButton } from '@/components/RefreshButton'
import { AssetsTable } from '@/features/catalog/AssetsTable'
import { useDatasets, useTables } from '@/features/catalog/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { useProjectFreshness } from '@/features/freshness/hooks'
import { SLA_LABELS } from '@/features/freshness/sla'
import { useRecordTableView } from '@/features/history/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatNumber } from '@/lib/format'

const MAX_AUTO_RECORDED_TABLE_VIEWS = 5

export function CatalogDatasetPage() {
  const { projectId } = useProjectContext()
  const { datasetId } = useParams<{ datasetId: string }>()
  const location = useLocation()
  const highlightTableId = (location.state as { highlightTable?: string } | null)?.highlightTable

  const tablesQuery = useTables(projectId, datasetId)
  const datasetsQuery = useDatasets(projectId)
  const freshnessQuery = useProjectFreshness(projectId)
  const recordTableView = useRecordTableView()

  // Registra as 5 primeiras tabelas visíveis como "visualizadas" — uma vez
  // por abertura do dataset (guardado por ref), não a cada refetch/refresh
  // manual (RefreshButton não deve gerar spam de eventos de histórico).
  // recordTableView.mutate não entra nas deps porque é uma nova referência
  // a cada render — incluí-la reexecutaria o efeito em loop.
  const recordedKeyRef = useRef<string | null>(null)
  // biome-ignore lint/correctness/useExhaustiveDependencies: ver comentário acima
  useEffect(() => {
    if (!tablesQuery.data || !projectId || !datasetId) return
    const key = `${projectId}:${datasetId}`
    if (recordedKeyRef.current === key) return
    recordedKeyRef.current = key
    for (const table of tablesQuery.data.tables.slice(0, MAX_AUTO_RECORDED_TABLE_VIEWS)) {
      recordTableView.mutate({ projectId, datasetId, tableId: table.table_id })
    }
  }, [tablesQuery.data, projectId, datasetId])

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

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{tablesQuery.data.dataset_id}</h1>
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
