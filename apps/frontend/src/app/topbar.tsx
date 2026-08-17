import { LogOut, Send, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { usePendingAccessRequests } from '@/features/admin/hooks'
import { RequestAccessDialog } from '@/features/admin/RequestAccessDialog'
import { useCurrentUser, useLogout } from '@/features/auth/hooks'
import { LogoutDialog } from '@/features/auth/LogoutDialog'
import { ProjectSelector } from '@/features/projects/ProjectSelector'

export function Topbar() {
  const userQuery = useCurrentUser()
  const logoutMutation = useLogout()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [requestAccessOpen, setRequestAccessOpen] = useState(false)
  const pendingQuery = usePendingAccessRequests()
  const pendingCount = pendingQuery.data?.requests.length ?? 0

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b-2 border-primary bg-background px-4">
      <div className="flex items-center gap-3">
        <span className="dp6-divider h-6 w-0.5 bg-primary" />
        <span className="text-lg font-bold tracking-wide">dp6</span>
      </div>

      <div className="h-6 w-px bg-border" />

      <ProjectSelector />

      <div className="ml-auto flex items-center gap-3">
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground"
                onClick={() => setRequestAccessOpen(true)}
                aria-label="Solicitar acesso a projetos"
              />
            }
          >
            <Send size={16} />
          </TooltipTrigger>
          <TooltipContent>Solicitar acesso a projetos</TooltipContent>
        </Tooltip>

        {userQuery.data?.is_admin && (
          <Tooltip>
            <TooltipTrigger
              render={
                <Link
                  to="/admin"
                  className="relative text-muted-foreground hover:text-foreground"
                />
              }
            >
              <ShieldCheck size={18} />
              {pendingCount > 0 && (
                <span
                  aria-hidden="true"
                  className="-top-1.5 -right-1.5 absolute flex size-4 items-center justify-center rounded-full bg-status-warn text-[10px] font-bold text-background"
                >
                  {pendingCount > 9 ? '9+' : pendingCount}
                </span>
              )}
            </TooltipTrigger>
            <TooltipContent>
              Administração
              {pendingCount > 0
                ? ` — ${pendingCount} solicitaç${pendingCount === 1 ? 'ão' : 'ões'} pendente${pendingCount === 1 ? '' : 's'}`
                : ''}
            </TooltipContent>
          </Tooltip>
        )}

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                variant="ghost"
                className="gap-2 text-muted-foreground"
                onClick={() => setConfirmOpen(true)}
                aria-label="Sair"
              />
            }
          >
            {userQuery.data?.picture && (
              <img
                src={userQuery.data.picture}
                alt=""
                referrerPolicy="no-referrer"
                className="size-6 rounded-full"
              />
            )}
            {userQuery.data && (
              <span className="text-sm">{userQuery.data.name || userQuery.data.email}</span>
            )}
            <LogOut size={16} />
          </TooltipTrigger>
          <TooltipContent>
            <div className="flex flex-col">
              {userQuery.data && <span>{userQuery.data.email}</span>}
              <span className="text-xs opacity-70">Clique para sair</span>
            </div>
          </TooltipContent>
        </Tooltip>
      </div>

      <LogoutDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        isLoggingOut={logoutMutation.isPending}
        onConfirm={() => logoutMutation.mutate()}
      />
      <RequestAccessDialog open={requestAccessOpen} onOpenChange={setRequestAccessOpen} />
    </header>
  )
}
