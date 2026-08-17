import { ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { useDatasets, useTables } from '@/features/catalog/hooks'
import type { DatasetSummary } from '@/types/catalog'

interface ColumnTypeScopePickerProps {
  projectId: string | undefined
  selected: Set<string>
  onChange: (next: Set<string>) => void
}

// Roda em produção com centenas/milhares de tabelas — escanear o
// projeto inteiro é inviável (custo real de TABLESAMPLE por tabela).
// Esse seletor obriga o usuário a escolher o escopo antes: dataset
// (marca todas as tabelas dele) e/ou tabela individual dentro do
// dataset. useTables roda sem gate de "expandido" — é INFORMATION_SCHEMA
// grátis (mesmo custo de listar o catálogo), então buscar a lista de
// tabelas de cada dataset renderizado aqui não tem o mesmo problema de
// custo do scan em si; evita também um estado "selecionar tudo" que
// dependeria de dado ainda não carregado.
export function ColumnTypeScopePicker({
  projectId,
  selected,
  onChange,
}: ColumnTypeScopePickerProps) {
  const datasetsQuery = useDatasets(projectId)
  const [expandedDatasets, setExpandedDatasets] = useState<Set<string>>(new Set())

  function toggleExpanded(datasetId: string) {
    setExpandedDatasets((current) => {
      const next = new Set(current)
      if (next.has(datasetId)) {
        next.delete(datasetId)
      } else {
        next.add(datasetId)
      }
      return next
    })
  }

  if (!projectId) return null

  if (datasetsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando datasets…</p>
  }

  return (
    <div className="flex max-h-64 flex-col gap-1 overflow-y-auto rounded-lg border border-border p-3">
      {(datasetsQuery.data?.datasets ?? []).map((dataset) => (
        <DatasetScopeRow
          key={dataset.dataset_id}
          projectId={projectId}
          dataset={dataset}
          expanded={expandedDatasets.has(dataset.dataset_id)}
          onToggleExpanded={() => toggleExpanded(dataset.dataset_id)}
          selected={selected}
          onChange={onChange}
        />
      ))}
      {datasetsQuery.data?.datasets.length === 0 && (
        <p className="text-sm text-muted-foreground">Nenhum dataset encontrado.</p>
      )}
    </div>
  )
}

function DatasetScopeRow({
  projectId,
  dataset,
  expanded,
  onToggleExpanded,
  selected,
  onChange,
}: {
  projectId: string
  dataset: DatasetSummary
  expanded: boolean
  onToggleExpanded: () => void
  selected: Set<string>
  onChange: (next: Set<string>) => void
}) {
  const tablesQuery = useTables(projectId, dataset.dataset_id)
  const tables = tablesQuery.data?.tables ?? []
  const tableKeys = tables.map((t) => `${dataset.dataset_id}.${t.table_id}`)
  const selectedCount = tableKeys.filter((key) => selected.has(key)).length
  const allSelected = tableKeys.length > 0 && selectedCount === tableKeys.length

  function toggleDataset() {
    if (tableKeys.length === 0) return
    const next = new Set(selected)
    if (allSelected) {
      for (const key of tableKeys) next.delete(key)
    } else {
      for (const key of tableKeys) next.add(key)
      if (!expanded) onToggleExpanded()
    }
    onChange(next)
  }

  function toggleTable(tableId: string) {
    const key = `${dataset.dataset_id}.${tableId}`
    const next = new Set(selected)
    if (next.has(key)) {
      next.delete(key)
    } else {
      next.add(key)
    }
    onChange(next)
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleExpanded}
          className="text-muted-foreground hover:text-foreground"
          aria-label={
            expanded
              ? `Recolher tabelas de ${dataset.dataset_id}`
              : `Expandir ${dataset.dataset_id}`
          }
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <Checkbox
          checked={allSelected}
          disabled={tablesQuery.isLoading}
          onCheckedChange={toggleDataset}
        />
        <button type="button" onClick={toggleDataset} className="text-sm hover:text-primary">
          {dataset.dataset_id}
        </button>
        <span className="text-xs text-muted-foreground">
          {selectedCount > 0
            ? `${selectedCount}/${dataset.total_tables} selecionadas`
            : `${dataset.total_tables} tabelas`}
        </span>
      </div>

      {expanded && (
        <div className="ml-8 flex flex-col gap-1">
          {tablesQuery.isLoading && (
            <p className="text-xs text-muted-foreground">Carregando tabelas…</p>
          )}
          {tables.map((table) => (
            <div key={table.table_id} className="flex items-center gap-2">
              <Checkbox
                checked={selected.has(`${dataset.dataset_id}.${table.table_id}`)}
                onCheckedChange={() => toggleTable(table.table_id)}
              />
              <button
                type="button"
                onClick={() => toggleTable(table.table_id)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {table.table_id}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
