import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AdminAccessRequestsTab } from '@/features/admin/AdminAccessRequestsTab'
import { AdminProjectsTab } from '@/features/admin/AdminProjectsTab'
import { AdminUsageTab } from '@/features/admin/AdminUsageTab'
import { AdminUsersTab } from '@/features/admin/AdminUsersTab'
import { usePendingAccessRequests } from '@/features/admin/hooks'

const USERS_TAB = 'users'
const PROJECTS_TAB = 'projects'
const REQUESTS_TAB = 'requests'
const USAGE_TAB = 'usage'

export function AdminPage() {
  const pendingQuery = usePendingAccessRequests()
  const pendingCount = pendingQuery.data?.requests.length ?? 0

  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/"
        className="flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft size={14} />
        Voltar
      </Link>

      <div>
        <h1 className="text-2xl font-bold">Administração — usuários e acesso</h1>
        <p className="text-sm text-muted-foreground">
          Controla quem é administrador do Hub e a quais projetos GCP cada usuário tem acesso. O
          login em si continua controlado pela allowlist do OAuth (fora daqui) — isto aqui só
          controla acesso a projeto dentro do Hub.
        </p>
      </div>

      <Tabs defaultValue={USERS_TAB}>
        <TabsList className="w-fit">
          <TabsTrigger value={USERS_TAB}>Por usuário</TabsTrigger>
          <TabsTrigger value={PROJECTS_TAB}>Por projeto</TabsTrigger>
          <TabsTrigger value={REQUESTS_TAB} className="gap-1.5">
            Solicitações
            {pendingCount > 0 && (
              <Badge
                variant="outline"
                className="border-status-warn/30 bg-status-warn/10 text-status-warn"
              >
                {pendingCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value={USAGE_TAB}>Uso do Hub</TabsTrigger>
        </TabsList>

        <TabsContent value={USERS_TAB}>
          <AdminUsersTab />
        </TabsContent>

        <TabsContent value={PROJECTS_TAB}>
          <AdminProjectsTab />
        </TabsContent>

        <TabsContent value={REQUESTS_TAB}>
          <AdminAccessRequestsTab />
        </TabsContent>

        <TabsContent value={USAGE_TAB}>
          <AdminUsageTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
