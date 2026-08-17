import { Pencil, Plus, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useDeleteHubUser, useHubUsers, useUpsertHubUser } from '@/features/admin/hooks'
import { formatDate } from '@/lib/format'
import { ApiError } from '@/lib/http-client'
import type { HubUser } from '@/types/admin'

export function AdminPage() {
  const usersQuery = useHubUsers()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<HubUser | null>(null)
  const [deletingEmail, setDeletingEmail] = useState<string | null>(null)

  function openCreateDialog() {
    setEditingUser(null)
    setDialogOpen(true)
  }

  function openEditDialog(user: HubUser) {
    setEditingUser(user)
    setDialogOpen(true)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Administração — usuários e acesso</h1>
          <p className="text-sm text-muted-foreground">
            Controla quem é administrador do Hub e a quais projetos GCP cada usuário tem acesso. O
            login em si continua controlado pela allowlist do OAuth (fora daqui) — isto aqui só
            controla acesso a projeto dentro do Hub.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <RefreshButton
            isRefreshing={usersQuery.isFetching}
            onRefresh={() => usersQuery.refetch()}
          />
          <Button onClick={openCreateDialog}>
            <Plus size={16} />
            Adicionar usuário
          </Button>
        </div>
      </div>

      {usersQuery.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {usersQuery.isError && <ApiErrorNotice error={usersQuery.error} />}

      {usersQuery.data && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>E-mail</TableHead>
              <TableHead>Admin</TableHead>
              <TableHead>Projetos liberados</TableHead>
              <TableHead>Atualizado</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {usersQuery.data.users.map((user) => (
              <TableRow key={user.email}>
                <TableCell className="font-medium">{user.email}</TableCell>
                <TableCell>
                  {user.is_admin ? (
                    <Badge>Admin</Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {user.allowed_projects.length === 0 && (
                      <span className="text-xs text-muted-foreground">Nenhum</span>
                    )}
                    {user.allowed_projects.map((p) => (
                      <Badge key={p} variant="outline">
                        {p === '*' ? 'Todos os projetos' : p}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatDate(user.updated_at)} por {user.updated_by}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`Editar ${user.email}`}
                      onClick={() => openEditDialog(user)}
                    >
                      <Pencil size={14} />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`Remover ${user.email}`}
                      onClick={() => setDeletingEmail(user.email)}
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {usersQuery.data.users.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground">
                  Nenhum usuário administrado ainda.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <UpsertUserDialog open={dialogOpen} onOpenChange={setDialogOpen} user={editingUser} />
      <DeleteUserDialog
        email={deletingEmail}
        onOpenChange={(open) => !open && setDeletingEmail(null)}
      />
    </div>
  )
}

function UpsertUserDialog({
  open,
  onOpenChange,
  user,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: HubUser | null
}) {
  const isEditing = user !== null
  const [email, setEmail] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const [projects, setProjects] = useState<string[]>([])
  const [projectInput, setProjectInput] = useState('')
  const upsertMutation = useUpsertHubUser()

  // Reset ao abrir (ou trocar de usuário sendo editado) — mutations do
  // TanStack Query não limpam sozinhas, mesmo motivo já documentado em
  // features/pii/PiiTab.tsx.
  // biome-ignore lint/correctness/useExhaustiveDependencies: ver comentário acima
  useEffect(() => {
    if (!open) return
    setEmail(user?.email ?? '')
    setIsAdmin(user?.is_admin ?? false)
    setProjects(user?.allowed_projects ?? [])
    setProjectInput('')
    upsertMutation.reset()
  }, [open, user])

  function addProject() {
    const value = projectInput.trim()
    if (!value || projects.includes(value)) return
    setProjects((current) => [...current, value])
    setProjectInput('')
  }

  function removeProject(value: string) {
    setProjects((current) => current.filter((p) => p !== value))
  }

  function handleSubmit() {
    const trimmedEmail = email.trim()
    if (!trimmedEmail) return
    upsertMutation.mutate(
      { email: trimmedEmail, request: { is_admin: isAdmin, allowed_projects: projects } },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  const errorMessage =
    upsertMutation.error instanceof ApiError
      ? upsertMutation.error.message
      : upsertMutation.error instanceof Error
        ? upsertMutation.error.message
        : null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Editar usuário' : 'Adicionar usuário'}</DialogTitle>
          <DialogDescription>
            Controla se este usuário é administrador do Hub e a quais projetos GCP ele tem acesso.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="admin-user-email">E-mail</Label>
            <Input
              id="admin-user-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isEditing}
              placeholder="usuario@dp6.com.br"
            />
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="admin-user-is-admin"
              checked={isAdmin}
              onCheckedChange={(checked) => setIsAdmin(checked === true)}
            />
            <Label htmlFor="admin-user-is-admin" className="cursor-pointer font-normal">
              Administrador do Hub
            </Label>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="admin-user-project">Projetos liberados</Label>
            <div className="flex gap-2">
              <Input
                id="admin-user-project"
                value={projectInput}
                onChange={(e) => setProjectInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addProject()
                  }
                }}
                placeholder="project-id ou * para todos"
              />
              <Button type="button" variant="outline" onClick={addProject}>
                Adicionar
              </Button>
            </div>
            <div className="flex flex-wrap gap-1">
              {projects.length === 0 && (
                <span className="text-xs text-muted-foreground">Nenhum projeto liberado.</span>
              )}
              {projects.map((p) => (
                <Badge key={p} variant="outline" className="gap-1">
                  {p === '*' ? 'Todos os projetos' : p}
                  <button
                    type="button"
                    onClick={() => removeProject(p)}
                    aria-label={`Remover ${p}`}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X size={10} />
                  </button>
                </Badge>
              ))}
            </div>
          </div>

          {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={upsertMutation.isPending || !email.trim()} onClick={handleSubmit}>
            {upsertMutation.isPending ? 'Salvando…' : 'Salvar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DeleteUserDialog({
  email,
  onOpenChange,
}: {
  email: string | null
  onOpenChange: (open: boolean) => void
}) {
  const deleteMutation = useDeleteHubUser()

  const errorMessage =
    deleteMutation.error instanceof ApiError
      ? deleteMutation.error.message
      : deleteMutation.error instanceof Error
        ? deleteMutation.error.message
        : null

  return (
    <Dialog open={email !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remover acesso</DialogTitle>
          <DialogDescription>
            {email} perde o acesso administrado a todos os projetos do Hub. O login continua valendo
            se o e-mail/domínio dele estiver na allowlist do OAuth — só o acesso a projeto (e/ou
            admin) é removido.
          </DialogDescription>
        </DialogHeader>
        {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={deleteMutation.isPending}
            onClick={() => {
              if (!email) return
              deleteMutation.mutate(email, { onSuccess: () => onOpenChange(false) })
            }}
          >
            {deleteMutation.isPending ? 'Removendo…' : 'Remover'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
