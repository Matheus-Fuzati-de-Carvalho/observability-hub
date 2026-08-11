import { Cloud } from 'lucide-react'
import { Outlet } from 'react-router-dom'
import { Topbar } from '@/app/topbar'
import { DatasetSidebar } from '@/features/catalog/DatasetSidebar'
import { useProjectContext } from '@/features/projects/ProjectContext'

export function AppLayout() {
  const { projectId } = useProjectContext()

  return (
    <div className="flex h-screen flex-col">
      <Topbar />
      <div className="flex min-h-0 flex-1">
        {projectId && <DatasetSidebar projectId={projectId} />}
        <main className="min-w-0 flex-1 overflow-y-auto p-6">
          {projectId ? (
            <Outlet />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-muted-foreground">
              <Cloud size={32} />
              <p className="text-lg">Digite um projeto GCP para começar</p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
