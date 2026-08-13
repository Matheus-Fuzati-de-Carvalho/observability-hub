const STORAGE_KEY = 'observability-hub:last-project-id'

export function setLastProjectId(projectId: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, projectId)
  } catch {
    // localStorage indisponível (modo privado, etc.) — não é crítico, só
    // perde o preenchimento automático do próximo acesso.
  }
}

export function getLastProjectId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function clearLastProjectId(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ver setLastProjectId
  }
}
