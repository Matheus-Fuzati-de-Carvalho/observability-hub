import { Cloud } from 'lucide-react'
import { Link } from 'react-router-dom'

interface TopbarProps {
  projectId: string
}

export function Topbar({ projectId }: TopbarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b-2 border-primary bg-background px-4">
      <div className="flex items-center gap-3">
        <span className="dp6-divider h-6 w-0.5 bg-primary" />
        <span className="text-lg font-bold tracking-wide">dp6</span>
      </div>

      <div className="h-6 w-px bg-border" />

      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Cloud size={16} />
        <span>GCP Project:</span>
        <Link to="/" className="font-medium text-foreground hover:text-primary">
          {projectId}
        </Link>
      </div>
    </header>
  )
}
