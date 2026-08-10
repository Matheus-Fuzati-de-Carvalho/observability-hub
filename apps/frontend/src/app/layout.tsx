import { Navigate, Outlet, useParams } from 'react-router-dom'
import { Topbar } from '@/app/topbar'
import { DatasetSidebar } from '@/features/catalog/DatasetSidebar'

export function AppLayout() {
  const { projectId } = useParams<{ projectId: string }>()

  if (!projectId) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex h-screen flex-col">
      <Topbar projectId={projectId} />
      <div className="flex min-h-0 flex-1">
        <DatasetSidebar projectId={projectId} />
        <main className="min-w-0 flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
