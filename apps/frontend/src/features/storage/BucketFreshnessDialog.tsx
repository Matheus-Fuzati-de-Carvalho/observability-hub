import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useBucketFreshness } from '@/features/storage/hooks'
import { formatDate } from '@/lib/format'
import { ApiError } from '@/lib/http-client'

interface BucketFreshnessDialogProps {
  bucketName: string | null
  onOpenChange: (open: boolean) => void
}

export function BucketFreshnessDialog({ bucketName, onOpenChange }: BucketFreshnessDialogProps) {
  const { projectId } = useProjectContext()
  const freshnessQuery = useBucketFreshness(projectId, bucketName)
  const errorMessage =
    freshnessQuery.error instanceof ApiError
      ? freshnessQuery.error.message
      : freshnessQuery.error instanceof Error
        ? freshnessQuery.error.message
        : null

  return (
    <Dialog open={Boolean(bucketName)} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Freshness de {bucketName}</DialogTitle>
        </DialogHeader>

        {freshnessQuery.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}

        {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}

        {freshnessQuery.data && (
          <div className="flex flex-col gap-3">
            <div>
              <p className="text-xs text-muted-foreground uppercase">Última modificação</p>
              <p className="text-lg font-medium">{formatDate(freshnessQuery.data.last_modified)}</p>
            </div>
            {freshnessQuery.data.warning && (
              <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
                {freshnessQuery.data.warning}
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
