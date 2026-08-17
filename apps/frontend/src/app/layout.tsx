import { Cloud } from 'lucide-react'
import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Topbar } from '@/app/topbar'
import { Button } from '@/components/ui/button'
import { RequestAccessDialog } from '@/features/admin/RequestAccessDialog'
import { DatasetSidebar } from '@/features/catalog/DatasetSidebar'
import { useProjectContext } from '@/features/projects/ProjectContext'

export function AppLayout() {
  const { projectId } = useProjectContext()
  const [requestAccessOpen, setRequestAccessOpen] = useState(false)

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
              <p className="text-sm">
                Não tem acesso a nenhum projeto ainda?{' '}
                <Button
                  variant="link"
                  className="h-auto p-0"
                  onClick={() => setRequestAccessOpen(true)}
                >
                  Solicite acesso
                </Button>
              </p>
            </div>
          )}
        </main>
      </div>
      <RequestAccessDialog open={requestAccessOpen} onOpenChange={setRequestAccessOpen} />
    </div>
  )
}
