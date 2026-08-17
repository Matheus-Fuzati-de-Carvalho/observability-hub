export interface Favorite {
  project_id: string
  dataset_id: string
  // null = favorito do dataset inteiro (não uma tabela específica).
  table_id: string | null
  nickname: string | null
  added_at: string
}

export interface FavoritesListResponse {
  favorites: Favorite[]
}
