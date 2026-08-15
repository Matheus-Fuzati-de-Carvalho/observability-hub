import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { TableHead } from '@/components/ui/table'
import { cn } from '@/lib/utils'

interface SortableTableHeadProps {
  label: string
  active: boolean
  direction: 'asc' | 'desc'
  onClick: () => void
  align?: 'left' | 'right'
}

export function SortableTableHead({
  label,
  active,
  direction,
  onClick,
  align = 'left',
}: SortableTableHeadProps) {
  return (
    <TableHead className={align === 'right' ? 'text-right' : undefined}>
      <button
        type="button"
        className={cn(
          'inline-flex items-center gap-1 hover:text-foreground',
          align === 'right' && 'flex-row-reverse',
        )}
        onClick={onClick}
      >
        {label}
        {active ? (
          direction === 'asc' ? (
            <ArrowUp size={12} />
          ) : (
            <ArrowDown size={12} />
          )
        ) : (
          <ArrowUpDown size={12} className="opacity-40" />
        )}
      </button>
    </TableHead>
  )
}
