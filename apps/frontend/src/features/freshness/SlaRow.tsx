import { SLA_LABELS, SLA_ORDER, SLA_TEXT_COLOR } from '@/features/freshness/sla'
import { cn } from '@/lib/utils'
import type { FreshnessCounts } from '@/types/freshness'

export function SlaRow({ counts }: { counts: FreshnessCounts }) {
  return (
    <div className="grid grid-cols-3 gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-6">
      {SLA_ORDER.map((status) => {
        const value = counts[status]
        return (
          <div key={status} className="text-center">
            <p className="mb-1 text-xs text-muted-foreground">{SLA_LABELS[status]}</p>
            <p
              className={cn(
                'text-xl font-bold',
                value > 0 ? SLA_TEXT_COLOR[status] : 'text-muted-foreground',
              )}
            >
              {value}
            </p>
          </div>
        )
      })}
    </div>
  )
}
