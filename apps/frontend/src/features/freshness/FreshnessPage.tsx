import { RefreshButton } from '@/components/RefreshButton'
import { DatasetFreshnessTable } from '@/features/freshness/DatasetFreshnessTable'
import { useProjectFreshness } from '@/features/freshness/hooks'
import { SlaRow } from '@/features/freshness/SlaRow'
import { SLA_ORDER } from '@/features/freshness/sla'
import { useProjectContext } from '@/features/projects/ProjectContext'
import type { FreshnessCounts } from '@/types/freshness'

export function FreshnessPage() {
  const { projectId } = useProjectContext()
  const freshnessQuery = useProjectFreshness(projectId)

  if (freshnessQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (freshnessQuery.isError || !freshnessQuery.data) {
    return <p className="text-status-error">Erro ao carregar o freshness do projeto.</p>
  }

  const totals: FreshnessCounts = freshnessQuery.data.datasets.reduce(
    (acc, dataset) => {
      acc.total_tables += dataset.total_tables
      for (const status of SLA_ORDER) acc[status] += dataset[status]
      return acc
    },
    {
      total_tables: 0,
      ok: 0,
      warning_12_24: 0,
      warning_24_48: 0,
      warning_48_7d: 0,
      warning_7d_1m: 0,
      stale: 0,
    },
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Freshness</h1>
          <p className="text-sm text-muted-foreground">
            {totals.total_tables} tabelas monitoradas em {freshnessQuery.data.datasets.length}{' '}
            datasets
          </p>
        </div>
        <RefreshButton
          isRefreshing={freshnessQuery.isFetching}
          onRefresh={() => freshnessQuery.refetch()}
        />
      </div>

      <SlaRow counts={totals} />

      <DatasetFreshnessTable datasets={freshnessQuery.data.datasets} />
    </div>
  )
}
