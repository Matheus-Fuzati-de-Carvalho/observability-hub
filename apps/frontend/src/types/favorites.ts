export interface FavoriteTable {
  project_id: string
  dataset_id: string
  table_id: string
  added_at: string
}

export interface FavoritesListResponse {
  favorites: FavoriteTable[]
}
