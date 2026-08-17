import { ChevronDown, ChevronRight } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'

interface CollapsibleSectionProps {
  title: ReactNode
  // 'section' = tópico de topo da aba (equivalente ao antigo <h2>).
  // 'subsection' = bloco nomeado dentro de um tópico (ex: "Bases mais
  // favoritadas", "Drill-down").
  variant?: 'section' | 'subsection'
  defaultOpen?: boolean
  // Conteúdo à direita do título (ex: toggle de agrupamento) — fica fora
  // do trigger, sempre visível e clicável mesmo com a seção fechada.
  actions?: ReactNode
  children: ReactNode
}

export function CollapsibleSection({
  title,
  variant = 'section',
  defaultOpen = true,
  actions,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  const isSection = variant === 'section'

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CollapsibleTrigger
          className={cn(
            'flex items-center gap-1.5 hover:text-foreground',
            isSection ? 'font-semibold text-lg' : 'text-sm text-muted-foreground',
          )}
        >
          {open ? (
            <ChevronDown size={isSection ? 16 : 14} />
          ) : (
            <ChevronRight size={isSection ? 16 : 14} />
          )}
          {title}
        </CollapsibleTrigger>
        {actions}
      </div>
      <CollapsibleContent className={cn('flex flex-col gap-4', isSection ? 'pt-4' : 'pt-2')}>
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}
