import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { useTableLineage } from '@/features/lineage/hooks'
import { LineageGraph } from '@/features/lineage/LineageGraph'

interface LineageTabProps {
  projectId: string
  datasetId: string
  tableId: string | null
}

export function LineageTab({ projectId, datasetId, tableId }: LineageTabProps) {
  const lineageQuery = useTableLineage(projectId, datasetId, tableId ?? undefined)

  if (lineageQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando lineage…</p>
  }

  if (lineageQuery.isError) {
    return <ApiErrorNotice error={lineageQuery.error} />
  }

  const data = lineageQuery.data
  if (!data) return null

  return (
    <div className="flex flex-col gap-4">
      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      {data.truncated && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          Grafo truncado em {data.max_hops} saltos — pode haver mais tabelas além do limite.
        </div>
      )}

      <LineageGraph data={data} />

      <p className="text-xs text-muted-foreground">
        Baseado em audit logs dos últimos {data.lookback_days} dias.
      </p>
    </div>
  )
}
