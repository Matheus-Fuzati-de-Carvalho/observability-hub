import { httpClient } from '@/lib/http-client'
import type { FavoritesListResponse, FavoriteTable } from '@/types/favorites'

export const favoritesApi = {
  list: () => httpClient.get<FavoritesListResponse>('/api/v1/favorites'),

  add: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.post<FavoriteTable>('/api/v1/favorites', {
      project_id: projectId,
      dataset_id: datasetId,
      table_id: tableId,
    }),

  remove: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.delete<undefined>(`/api/v1/favorites/${projectId}/${datasetId}/${tableId}`),
}
