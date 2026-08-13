import { LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useCurrentUser, useLogout } from '@/features/auth/hooks'
import { ProjectSelector } from '@/features/projects/ProjectSelector'

export function Topbar() {
  const userQuery = useCurrentUser()
  const logoutMutation = useLogout()

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b-2 border-primary bg-background px-4">
      <div className="flex items-center gap-3">
        <span className="dp6-divider h-6 w-0.5 bg-primary" />
        <span className="text-lg font-bold tracking-wide">dp6</span>
      </div>

      <div className="h-6 w-px bg-border" />

      <ProjectSelector />

      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              variant="ghost"
              className="ml-auto gap-2 text-muted-foreground"
              disabled={logoutMutation.isPending}
              onClick={() => logoutMutation.mutate()}
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
        <TooltipContent>Sair{userQuery.data && ` — ${userQuery.data.email}`}</TooltipContent>
      </Tooltip>
    </header>
  )
}
