import { Database } from 'lucide-react'

export function CatalogOverviewPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
      <Database size={32} className="mb-3" />
      <p className="text-lg">Selecione um dataset na barra lateral</p>
      <p className="text-sm">para ver o catálogo de tabelas e views.</p>
    </div>
  )
}
