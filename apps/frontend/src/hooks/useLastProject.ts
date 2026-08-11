const STORAGE_KEY = 'observability-hub:last-project-id'

export function setLastProjectId(projectId: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, projectId)
  } catch {
    // localStorage indisponível (modo privado, etc.) — não é crítico, só
    // perde o preenchimento automático do próximo acesso.
  }
}
