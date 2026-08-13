import { useParams } from 'react-router-dom'
import { RefreshButton } from '@/components/RefreshButton'
import { useDatasetFreshness } from '@/features/freshness/hooks'
import { SlaRow } from '@/features/freshness/SlaRow'
import { TableFreshnessTable } from '@/features/freshness/TableFreshnessTable'
import { useProjectContext } from '@/features/projects/ProjectContext'

export function DatasetFreshnessPage() {
  const { projectId } = useProjectContext()
  const { datasetId } = useParams<{ datasetId: string }>()
  const freshnessQuery = useDatasetFreshness(projectId, datasetId)

  if (freshnessQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (freshnessQuery.isError || !freshnessQuery.data) {
    return <p className="text-status-error">Erro ao carregar o freshness do dataset.</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{freshnessQuery.data.dataset_id}</h1>
          <p className="text-sm text-muted-foreground">
            Freshness de {freshnessQuery.data.tables.length}{' '}
            {freshnessQuery.data.tables.length === 1 ? 'tabela' : 'tabelas'} —{' '}
            {freshnessQuery.data.location}
          </p>
        </div>
        <RefreshButton
          isRefreshing={freshnessQuery.isFetching}
          onRefresh={() => freshnessQuery.refetch()}
        />
      </div>

      <SlaRow counts={freshnessQuery.data.summary} />

      <TableFreshnessTable tables={freshnessQuery.data.tables} />
    </div>
  )
}
