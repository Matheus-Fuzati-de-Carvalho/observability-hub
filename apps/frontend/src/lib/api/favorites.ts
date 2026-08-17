import { httpClient } from '@/lib/http-client'
import type { Favorite, FavoritesListResponse } from '@/types/favorites'

export const favoritesApi = {
  list: () => httpClient.get<FavoritesListResponse>('/api/v1/favorites'),

  // table_id null favorita o dataset inteiro. nickname omitido preserva o
  // apelido já salvo (upsert idempotente) — string vazia limpa o apelido.
  add: (projectId: string, datasetId: string, tableId: string | null, nickname?: string) =>
    httpClient.post<Favorite>('/api/v1/favorites', {
      project_id: projectId,
      dataset_id: datasetId,
      table_id: tableId,
      nickname,
    }),

  removeTable: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.delete<undefined>(`/api/v1/favorites/${projectId}/${datasetId}/${tableId}`),

  removeDataset: (projectId: string, datasetId: string) =>
    httpClient.delete<undefined>(`/api/v1/favorites/${projectId}/${datasetId}`),
}
