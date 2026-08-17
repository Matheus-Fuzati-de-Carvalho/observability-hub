import { ChevronDown, ChevronRight, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  useGrantProjectAccess,
  useHubProjects,
  useProjectUsers,
  useRevokeProjectAccess,
  useUpsertHubProject,
} from '@/features/admin/hooks'
import { ApiError } from '@/lib/http-client'
import type { HubProject } from '@/types/admin'

// Visão inversa da aba "Por usuário" (usuário -> projetos): aqui é
// projeto -> usuários, mais o eixo "liberado a todos" (hub_projects),
// que não existe do lado do usuário — cobre acesso público, inclusive
// pra quem ainda não tem doc em hub_users.
export function AdminProjectsTab() {
  const projectsQuery = useHubProjects()
  const upsertProjectMutation = useUpsertHubProject()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [newProjectId, setNewProjectId] = useState('')

  function toggleExpanded(projectId: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(projectId)) {
        next.delete(projectId)
      } else {
        next.add(projectId)
      }
      return next
    })
  }

  function registerProject() {
    const value = newProjectId.trim()
    if (!value) return
    upsertProjectMutation.mutate(
      { projectId: value, request: { is_public: false } },
      {
        onSuccess: () => {
          setNewProjectId('')
          setExpanded((current) => new Set(current).add(value))
        },
      },
    )
  }

  return (
    <div className="mt-4 flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        "Liberado a todos" vale pra qualquer usuário do Hub, inclusive quem ainda não tem cadastro —
        independente da lista de projetos de cada usuário na aba "Por usuário".
      </p>

      <div className="flex items-center gap-2">
        <Input
          value={newProjectId}
          onChange={(e) => setNewProjectId(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              registerProject()
            }
          }}
          placeholder="project-id"
          className="max-w-xs"
        />
        <Button
          type="button"
          variant="outline"
          disabled={!newProjectId.trim() || upsertProjectMutation.isPending}
          onClick={registerProject}
        >
          <Plus size={16} />
          Registrar projeto
        </Button>
        <RefreshButton
          isRefreshing={projectsQuery.isFetching}
          onRefresh={() => projectsQuery.refetch()}
        />
      </div>

      {projectsQuery.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {projectsQuery.isError && <ApiErrorNotice error={projectsQuery.error} />}

      {projectsQuery.data && (
        <div className="flex flex-col gap-1">
          {projectsQuery.data.projects.map((project) => (
            <ProjectRow
              key={project.project_id}
              project={project}
              expanded={expanded.has(project.project_id)}
              onToggleExpanded={() => toggleExpanded(project.project_id)}
            />
          ))}
          {projectsQuery.data.projects.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nenhum projeto registrado ainda — registre um acima.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function ProjectRow({
  project,
  expanded,
  onToggleExpanded,
}: {
  project: HubProject
  expanded: boolean
  onToggleExpanded: () => void
}) {
  const upsertProjectMutation = useUpsertHubProject()

  return (
    <div className="rounded-md border border-border">
      <div className="flex items-center gap-3 px-3 py-2">
        <button
          type="button"
          onClick={onToggleExpanded}
          className="text-muted-foreground hover:text-foreground"
          aria-label={
            expanded ? `Recolher ${project.project_id}` : `Expandir ${project.project_id}`
          }
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="flex-1 text-sm font-medium">{project.project_id}</span>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Checkbox
            id={`public-${project.project_id}`}
            checked={project.is_public}
            disabled={upsertProjectMutation.isPending}
            onCheckedChange={() =>
              upsertProjectMutation.mutate({
                projectId: project.project_id,
                request: { is_public: !project.is_public },
              })
            }
          />
          <label htmlFor={`public-${project.project_id}`} className="cursor-pointer">
            Liberado a todos
          </label>
        </div>
      </div>
      {expanded && <ProjectUsersDetail projectId={project.project_id} />}
    </div>
  )
}

function ProjectUsersDetail({ projectId }: { projectId: string }) {
  const usersQuery = useProjectUsers(projectId)
  const grantMutation = useGrantProjectAccess()
  const revokeMutation = useRevokeProjectAccess()
  const [email, setEmail] = useState('')

  const errorMessage =
    grantMutation.error instanceof ApiError
      ? grantMutation.error.message
      : revokeMutation.error instanceof ApiError
        ? revokeMutation.error.message
        : null

  function grant() {
    const value = email.trim()
    if (!value) return
    grantMutation.mutate({ projectId, email: value }, { onSuccess: () => setEmail('') })
  }

  return (
    <div className="border-t border-border bg-muted/30 px-3 py-3">
      {usersQuery.isLoading && <p className="text-xs text-muted-foreground">Carregando…</p>}

      {usersQuery.data && (
        <div className="flex flex-col gap-1">
          {usersQuery.data.users.length === 0 && (
            <p className="text-xs text-muted-foreground">Nenhum acesso explícito concedido.</p>
          )}
          {usersQuery.data.users.map((userGrant) => (
            <div key={userGrant.email} className="flex items-center gap-2 text-xs">
              <span className="flex-1">{userGrant.email}</span>
              {userGrant.is_admin && <Badge variant="outline">Admin</Badge>}
              <Badge variant="outline">
                {userGrant.granted_via === 'wildcard' ? 'todos os projetos (*)' : 'este projeto'}
              </Badge>
              {userGrant.granted_via === 'explicit' && (
                <button
                  type="button"
                  onClick={() => revokeMutation.mutate({ projectId, email: userGrant.email })}
                  aria-label={`Remover acesso de ${userGrant.email}`}
                  className="text-muted-foreground hover:text-status-error"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-2 flex gap-2">
        <Input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              grant()
            }
          }}
          placeholder="conceder a um e-mail…"
          className="h-8 text-xs"
        />
        <Button
          size="sm"
          variant="outline"
          disabled={!email.trim() || grantMutation.isPending}
          onClick={grant}
        >
          Conceder
        </Button>
      </div>
      {errorMessage && <p className="mt-1 text-xs text-status-error">{errorMessage}</p>}
    </div>
  )
}
