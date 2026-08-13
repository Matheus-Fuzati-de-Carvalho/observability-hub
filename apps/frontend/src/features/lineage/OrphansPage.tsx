import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useOrphans } from '@/features/lineage/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'

export function OrphansPage() {
  const { projectId } = useProjectContext()
  const orphansQuery = useOrphans(projectId)

  if (orphansQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (orphansQuery.isError) {
    return <ApiErrorNotice error={orphansQuery.error} />
  }

  const data = orphansQuery.data
  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tabelas órfãs</h1>
          <p className="text-sm text-muted-foreground">
            {data.orphans.length} tabelas sem consumidor conhecido nos últimos {data.lookback_days}{' '}
            dias
          </p>
        </div>
        <RefreshButton
          isRefreshing={orphansQuery.isFetching}
          onRefresh={() => orphansQuery.refetch()}
        />
      </div>

      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Dataset</TableHead>
            <TableHead>Tabela</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.orphans.map((orphan) => (
            <TableRow key={`${orphan.dataset_id}.${orphan.table_id}`}>
              <TableCell>
                <Link to={`/datasets/${orphan.dataset_id}`} className="hover:text-primary">
                  {orphan.dataset_id}
                </Link>
              </TableCell>
              <TableCell className="font-medium">{orphan.table_id}</TableCell>
            </TableRow>
          ))}
          {data.orphans.length === 0 && (
            <TableRow>
              <TableCell colSpan={2} className="text-center text-muted-foreground">
                Nenhuma tabela órfã encontrada.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
