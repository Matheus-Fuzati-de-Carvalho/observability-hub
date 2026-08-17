import { useState } from 'react'

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const
export type PageSize = (typeof PAGE_SIZE_OPTIONS)[number]

interface UsePaginationOptions {
  rowCount: number
  initialPageSize?: PageSize
}

/**
 * Paginação real (com Anterior/Próxima) sobre uma lista já carregada
 * inteira no cliente — não pede mais dados ao backend, só corta o array
 * já em mãos. `page` fica sempre dentro de [0, pageCount) mesmo se
 * `rowCount` encolher (ex: um filtro reduz o total) porque é recalculado
 * a cada render a partir do `rowCount` atual.
 */
export function usePagination({ rowCount, initialPageSize = 20 }: UsePaginationOptions) {
  const [pageSize, setPageSizeState] = useState<PageSize>(initialPageSize)
  const [rawPage, setRawPage] = useState(0)

  const pageCount = Math.max(1, Math.ceil(rowCount / pageSize))
  const page = Math.min(rawPage, pageCount - 1)
  const start = page * pageSize
  const end = Math.min(start + pageSize, rowCount)

  function setPageSize(size: PageSize) {
    setPageSizeState(size)
    setRawPage(0)
  }

  return {
    page,
    pageCount,
    pageSize,
    setPageSize,
    start,
    end,
    goToPreviousPage: () => setRawPage((p) => Math.max(p - 1, 0)),
    goToNextPage: () => setRawPage((p) => Math.min(p + 1, pageCount - 1)),
    // Usado quando o conjunto de dados muda por um motivo alheio a
    // filtro/ordenação normal (ex: trocou o modo de agrupamento) —
    // volta pra primeira página em vez de deixar `page` "grudado" numa
    // posição que não faz mais sentido pro novo conjunto.
    resetPage: () => setRawPage(0),
  }
}
