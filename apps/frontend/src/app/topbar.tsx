import { LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
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

      <div className="ml-auto flex items-center gap-3">
        {userQuery.data && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {userQuery.data.picture && (
              <img
                src={userQuery.data.picture}
                alt=""
                referrerPolicy="no-referrer"
                className="size-6 rounded-full"
              />
            )}
            <span>{userQuery.data.name || userQuery.data.email}</span>
          </div>
        )}
        <Button
          size="icon-sm"
          variant="ghost"
          disabled={logoutMutation.isPending}
          onClick={() => logoutMutation.mutate()}
          aria-label="Sair"
        >
          <LogOut size={16} />
        </Button>
      </div>
    </header>
  )
}
