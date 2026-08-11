import { ProjectSelector } from '@/features/projects/ProjectSelector'

export function Topbar() {
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b-2 border-primary bg-background px-4">
      <div className="flex items-center gap-3">
        <span className="dp6-divider h-6 w-0.5 bg-primary" />
        <span className="text-lg font-bold tracking-wide">dp6</span>
      </div>

      <div className="h-6 w-px bg-border" />

      <ProjectSelector />
    </header>
  )
}
