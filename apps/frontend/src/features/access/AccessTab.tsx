import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useTableAccess } from '@/features/access/hooks'
import { formatDate, formatNumber } from '@/lib/format'
import type { AccessType } from '@/types/access'

interface AccessTabProps {
  projectId: string
  datasetId: string
  tableId: string | null
}

const ACCESS_TYPE_LABELS: Record<AccessType, string> = {
  read: 'Leitura',
  write: 'Escrita',
}

export function AccessTab({ projectId, datasetId, tableId }: AccessTabProps) {
  const accessQuery = useTableAccess(projectId, datasetId, tableId ?? undefined)

  if (accessQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando acessos…</p>
  }

  if (accessQuery.isError) {
    return <ApiErrorNotice error={accessQuery.error} />
  }

  const data = accessQuery.data
  if (!data) return null

  return (
    <div className="flex flex-col gap-4">
      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      {data.users.length === 0 && !data.warning ? (
        <p className="text-sm text-muted-foreground">
          Nenhum acesso encontrado nos últimos {data.lookback_days} dias.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Usuário</TableHead>
              <TableHead className="text-xs">Último acesso</TableHead>
              <TableHead className="text-xs">Tipo</TableHead>
              <TableHead className="text-xs text-right">Acessos</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.users.map((user) => (
              <TableRow key={user.principal_email}>
                <TableCell className="text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{user.principal_email}</span>
                    <Badge variant={user.is_service_account ? 'outline' : 'default'}>
                      {user.is_service_account ? 'Service account' : 'Humano'}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatDate(user.last_accessed_at)}
                </TableCell>
                <TableCell className="text-xs">
                  <div className="flex flex-wrap gap-1">
                    {user.access_types.map((type) => (
                      <Badge key={type} variant="outline">
                        {ACCESS_TYPE_LABELS[type]}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="text-xs text-right">
                  {formatNumber(user.access_count)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <p className="text-xs text-muted-foreground">
        Baseado em audit logs dos últimos {data.lookback_days} dias.
      </p>
    </div>
  )
}
