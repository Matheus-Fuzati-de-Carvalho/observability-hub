import { Progress as ProgressPrimitive } from '@base-ui/react/progress'
import { ProgressIndicator, ProgressTrack } from '@/components/ui/progress'
import { cn } from '@/lib/utils'
import type { QualityFlag } from '@/types/profiling'

const FLAG_COLOR: Record<QualityFlag, string> = {
  ok: 'bg-status-ok',
  warning: 'bg-status-warn',
  critical: 'bg-status-error',
}

interface CompletenessBarProps {
  value: number
  flag: QualityFlag
}

export function CompletenessBar({ value, flag }: CompletenessBarProps) {
  return (
    <div className="flex items-center gap-2">
      <ProgressPrimitive.Root value={value} className="w-20">
        <ProgressTrack>
          <ProgressIndicator className={cn(FLAG_COLOR[flag])} />
        </ProgressTrack>
      </ProgressPrimitive.Root>
      <span className="text-xs tabular-nums text-muted-foreground">{value.toFixed(1)}%</span>
    </div>
  )
}
