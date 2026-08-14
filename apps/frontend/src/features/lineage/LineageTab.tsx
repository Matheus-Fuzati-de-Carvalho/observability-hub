import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { useTableLineage } from '@/features/lineage/hooks'
import type { TableRef } from '@/types/lineage'

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

      <div className="grid grid-cols-2 gap-4">
        <TableRefList title="Upstream (fontes)" refs={data.upstream} />
        <TableRefList title="Downstream (consumidores)" refs={data.downstream} />
      </div>

      <p className="text-xs text-muted-foreground">
        Baseado em audit logs dos últimos {data.lookback_days} dias.
      </p>
    </div>
  )
}

function TableRefList({ title, refs }: { title: string; refs: TableRef[] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </p>
      {refs.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma tabela encontrada.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {refs.map((ref) => (
            <li key={`${ref.project_id}.${ref.dataset_id}.${ref.table_id}`} className="text-sm">
              {ref.project_id}.{ref.dataset_id}.{ref.table_id}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
