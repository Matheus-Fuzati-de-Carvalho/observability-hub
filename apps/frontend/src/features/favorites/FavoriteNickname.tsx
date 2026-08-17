import { Pencil } from 'lucide-react'
import { type KeyboardEvent, useState } from 'react'
import { Input } from '@/components/ui/input'

interface FavoriteNicknameProps {
  nickname: string | null
  onSave: (nickname: string) => void
}

// Edição inline (sem dialog): lápis aparece no hover do item pai (o
// consumidor precisa ter `group` na linha), clique troca o texto por um
// input autofocado. Salva em blur/Enter, cancela em Escape sem salvar.
export function FavoriteNickname({ nickname, onSave }: FavoriteNicknameProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(nickname ?? '')

  function startEditing() {
    setDraft(nickname ?? '')
    setEditing(true)
  }

  function commit() {
    setEditing(false)
    if (draft !== (nickname ?? '')) {
      onSave(draft)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.currentTarget.blur()
    } else if (e.key === 'Escape') {
      setDraft(nickname ?? '')
      setEditing(false)
    }
  }

  if (editing) {
    return (
      <Input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={handleKeyDown}
        onClick={(e) => e.preventDefault()}
        placeholder="Apelido…"
        className="h-6 px-1.5 text-xs"
      />
    )
  }

  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      {nickname && <span className="truncate">{nickname}</span>}
      <button
        type="button"
        aria-label={nickname ? 'Editar apelido' : 'Adicionar apelido'}
        onClick={(e) => {
          e.preventDefault()
          startEditing()
        }}
        className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100 hover:text-foreground"
      >
        <Pencil size={11} />
      </button>
    </span>
  )
}
