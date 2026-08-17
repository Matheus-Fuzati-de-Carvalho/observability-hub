import { X } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface ProjectChipEditorProps {
  chips: string[]
  onChange: (next: string[]) => void
  placeholder?: string
  emptyLabel?: string
  inputId?: string
}

// Editor de "digite um project_id, Enter/botão adiciona, X remove" —
// compartilhado entre UpsertUserDialog (AdminPage.tsx) e
// RequestAccessDialog.tsx, mesma UI nos dois casos, só o destino da
// lista de project_id muda.
export function ProjectChipEditor({
  chips,
  onChange,
  placeholder = 'project-id ou * para todos',
  emptyLabel = 'Nenhum projeto.',
  inputId,
}: ProjectChipEditorProps) {
  const [input, setInput] = useState('')

  function addChip() {
    const value = input.trim()
    if (!value || chips.includes(value)) return
    onChange([...chips, value])
    setInput('')
  }

  function removeChip(value: string) {
    onChange(chips.filter((c) => c !== value))
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Input
          id={inputId}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addChip()
            }
          }}
          placeholder={placeholder}
        />
        <Button type="button" variant="outline" onClick={addChip}>
          Adicionar
        </Button>
      </div>
      <div className="flex flex-wrap gap-1">
        {chips.length === 0 && <span className="text-xs text-muted-foreground">{emptyLabel}</span>}
        {chips.map((c) => (
          <Badge key={c} variant="outline" className="gap-1">
            {c === '*' ? 'Todos os projetos' : c}
            <button
              type="button"
              onClick={() => removeChip(c)}
              aria-label={`Remover ${c}`}
              className="text-muted-foreground hover:text-foreground"
            >
              <X size={10} />
            </button>
          </Badge>
        ))}
      </div>
    </div>
  )
}
