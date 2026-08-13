import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { QualityScoreResponse } from '@/types/quality'

interface ScoreTier {
  label: string
  className: string
}

function tierFor(score: number): ScoreTier {
  if (score >= 80)
    return { label: 'Alta', className: 'border-status-ok/30 bg-status-ok/10 text-status-ok' }
  if (score >= 60) {
    return { label: 'Média', className: 'border-status-warn/30 bg-status-warn/10 text-status-warn' }
  }
  if (score >= 40)
    return { label: 'Baixa', className: 'border-orange-500/30 bg-orange-500/10 text-orange-600' }
  return {
    label: 'Crítica',
    className: 'border-status-error/30 bg-status-error/10 text-status-error',
  }
}

interface ScoreBadgeProps {
  data: QualityScoreResponse | undefined
  isLoading: boolean
}

export function ScoreBadge({ data, isLoading }: ScoreBadgeProps) {
  if (isLoading || !data) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        —
      </Badge>
    )
  }

  const tier = tierFor(data.score)

  return (
    <Tooltip>
      <TooltipTrigger>
        <Badge variant="outline" className={cn('font-medium', tier.className)}>
          {data.score} · {tier.label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        <div className="space-y-0.5">
          <div>Completude: {data.breakdown.completeness.toFixed(0)}%</div>
          <div>Freshness: {data.breakdown.freshness.toFixed(0)}%</div>
          <div>Duplicatas: {data.breakdown.duplicates.toFixed(0)}%</div>
          <div>Documentação: {data.breakdown.documentation.toFixed(0)}%</div>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
