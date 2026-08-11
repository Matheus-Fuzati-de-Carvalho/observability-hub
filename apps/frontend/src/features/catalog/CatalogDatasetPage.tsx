import { useParams } from 'react-router-dom'
import { AssetsTable } from '@/features/catalog/AssetsTable'
import { useDatasets, useTables } from '@/features/catalog/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { useProjectFreshness } from '@/features/freshness/hooks'
import { SLA_LABELS } from '@/features/freshness/sla'
import { formatNumber } from '@/lib/format'

export function CatalogDatasetPage() {
  const { projectId, datasetId } = useParams<{ projectId: string; datasetId: string }>()

  const tablesQuery = useTables(projectId, datasetId)
  const datasetsQuery = useDatasets(projectId)
  const freshnessQuery = useProjectFreshness(projectId)

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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">{tablesQuery.data.dataset_id}</h1>
        <p className="text-sm text-muted-foreground">{tablesQuery.data.total_tables} ativos</p>
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
      />
    </div>
  )
}
