import { RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface RefreshButtonProps {
  onRefresh: () => void
  isRefreshing: boolean
}

export function RefreshButton({ onRefresh, isRefreshing }: RefreshButtonProps) {
  return (
    <Button
      size="icon-sm"
      variant="ghost"
      disabled={isRefreshing}
      onClick={onRefresh}
      aria-label="Atualizar dados"
    >
      <RotateCcw className={cn(isRefreshing && 'animate-spin')} size={16} />
    </Button>
  )
}
