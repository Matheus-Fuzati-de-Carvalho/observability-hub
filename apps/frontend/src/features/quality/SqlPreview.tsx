import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

export function SqlPreview({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false)

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
        <Button size="sm" variant="ghost" onClick={handleCopy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? 'Copiado' : 'Copiar SQL'}
        </Button>
      </div>
      <pre className="max-h-48 overflow-y-auto overflow-x-auto font-mono text-xs whitespace-pre-wrap text-foreground">
        {sql}
      </pre>
    </div>
  )
}
