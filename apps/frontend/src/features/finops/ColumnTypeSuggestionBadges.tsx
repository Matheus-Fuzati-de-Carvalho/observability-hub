import { Badge } from '@/components/ui/badge'
import type { ColumnTypeSuggestion } from '@/types/finops'

export function ColumnTypeSuggestionBadges({
  suggestions,
}: {
  suggestions: ColumnTypeSuggestion[]
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {suggestions.map((s) => (
        <Badge
          key={s.column_name}
          variant="outline"
          title={`${s.sample_non_null_count} valores amostrados — ${s.avg_current_bytes.toFixed(1)}B → ${s.suggested_type_bytes}B`}
        >
          {s.column_name} → {s.suggested_type}
        </Badge>
      ))}
    </div>
  )
}
