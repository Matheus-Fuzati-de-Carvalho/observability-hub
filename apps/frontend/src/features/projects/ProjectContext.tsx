import { createContext, type ReactNode, useContext, useState } from 'react'

interface ProjectContextValue {
  projectId: string | undefined
  setProjectId: (projectId: string) => void
}

const ProjectContext = createContext<ProjectContextValue | null>(null)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projectId, setProjectId] = useState<string | undefined>(undefined)

  return (
    <ProjectContext.Provider value={{ projectId, setProjectId }}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProjectContext(): ProjectContextValue {
  const context = useContext(ProjectContext)
  if (!context) {
    throw new Error('useProjectContext deve ser usado dentro de um ProjectProvider')
  }
  return context
}
