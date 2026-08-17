import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { PAGE_SIZE_OPTIONS, type PageSize } from '@/hooks/usePagination'

interface PaginationBarProps {
  page: number
  pageCount: number
  pageSize: PageSize
  setPageSize: (size: PageSize) => void
  start: number
  end: number
  totalCount: number
  onPrevious: () => void
  onNext: () => void
}

export function PaginationBar({
  page,
  pageCount,
  pageSize,
  setPageSize,
  start,
  end,
  totalCount,
  onPrevious,
  onNext,
}: PaginationBarProps) {
  if (totalCount === 0) return null

  return (
    <div className="mt-2 flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
      <div className="flex items-center gap-2">
        <span>Linhas por página</span>
        <Select
          value={String(pageSize)}
          onValueChange={(value) => setPageSize(Number(value) as PageSize)}
        >
          <SelectTrigger className="w-20" size="sm">
            <SelectValue>{() => String(pageSize)}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {PAGE_SIZE_OPTIONS.map((size) => (
              <SelectItem key={size} value={String(size)}>
                {size}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span>
          {start + 1}–{end} de {totalCount}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" disabled={page === 0} onClick={onPrevious}>
          <ChevronLeft size={14} />
        </Button>
        <span>
          Página {page + 1} de {pageCount}
        </span>
        <Button size="sm" variant="outline" disabled={page >= pageCount - 1} onClick={onNext}>
          <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  )
}
