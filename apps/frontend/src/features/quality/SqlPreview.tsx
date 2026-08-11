import { Check, ChevronDown, ChevronUp, Copy } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

export function SqlPreview({ sql, defaultOpen = true }: { sql: string; defaultOpen?: boolean }) {
  const [copied, setCopied] = useState(false)
  const [open, setOpen] = useState(defaultOpen)

  async function handleCopy() {
    await navigator.clipboard.writeText(sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="rounded-md bg-background p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          SQL gerado
        </span>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={() => setOpen((v) => !v)}>
            {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {open ? 'Ocultar SQL' : 'Ver SQL'}
          </Button>
          <Button size="sm" variant="ghost" onClick={handleCopy}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? 'Copiado' : 'Copiar SQL'}
          </Button>
        </div>
      </div>
      {open && (
        <pre className="max-h-48 overflow-y-auto overflow-x-auto font-mono text-xs whitespace-pre-wrap text-foreground">
          {sql}
        </pre>
      )}
    </div>
  )
}
