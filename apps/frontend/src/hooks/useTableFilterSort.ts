import { useMemo, useState } from 'react'

type SortDirection = 'asc' | 'desc'

interface UseTableFilterSortOptions<T, K extends string> {
  rows: T[]
  initialSortKey: K
  compare: (a: T, b: T, key: K) => number
  matches: (row: T, search: string) => boolean
}

/**
 * Busca por texto + ordenação por coluna clicável — mesmo pipeline
 * (filtrar, depois ordenar) já usado em AssetsTable/TableFreshnessTable/
 * DatasetFreshnessTable, mas centralizado aqui em vez de duplicado por
 * tabela. `matches` cobre a busca por texto; filtros adicionais (ex: um
 * <Select> por tipo/status) continuam como useState local do
 * componente, combinados dentro do próprio `matches`.
 */
export function useTableFilterSort<T, K extends string>({
  rows,
  initialSortKey,
  compare,
  matches,
}: UseTableFilterSortOptions<T, K>) {
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<K>(initialSortKey)
  const [sortDir, setSortDir] = useState<SortDirection>('asc')

  function toggleSort(key: K) {
    if (key === sortKey) {
      setSortDir((direction) => (direction === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const visibleRows = useMemo(() => {
    const filtered = rows.filter((row) => matches(row, search))
    const sign = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey))
    // matches/compare quase sempre são closures novas a cada render (fecham
    // sobre filtros locais do chamador, ex: um <Select> de tipo) — incluídas
    // nas deps de propósito, correção > memoização aqui (tabelas pequenas).
  }, [rows, search, sortKey, sortDir, matches, compare])

  return { search, setSearch, sortKey, sortDir, toggleSort, visibleRows }
}
