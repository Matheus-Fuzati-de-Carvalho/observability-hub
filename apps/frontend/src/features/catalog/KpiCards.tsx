import { cn } from '@/lib/utils'

interface Kpi {
  label: string
  value: string
  alert?: boolean
}

export function KpiCards({ items }: { items: Kpi[] }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((item) => (
        <div
          key={item.label}
          className={cn(
            'rounded-lg border bg-card p-3',
            item.alert ? 'border-status-error' : 'border-border',
          )}
        >
          <p className="mb-0.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {item.label}
          </p>
          <p className="text-xl font-bold">{item.value}</p>
        </div>
      ))}
    </div>
  )
}
