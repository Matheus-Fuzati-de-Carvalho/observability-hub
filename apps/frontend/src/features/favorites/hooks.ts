import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { favoritesApi } from '@/lib/api/favorites'
import type { Favorite, FavoritesListResponse } from '@/types/favorites'

export const FAVORITES_QUERY_KEY = ['favorites']

export function useFavorites() {
  return useQuery({
    queryKey: FAVORITES_QUERY_KEY,
    queryFn: favoritesApi.list,
  })
}

export function isFavoriteTable(
  favorites: FavoritesListResponse | undefined,
  projectId: string,
  datasetId: string,
  tableId: string,
): boolean {
  return Boolean(
    favorites?.favorites.some(
      (f) => f.project_id === projectId && f.dataset_id === datasetId && f.table_id === tableId,
    ),
  )
}

export function isFavoriteDataset(
  favorites: FavoritesListResponse | undefined,
  projectId: string,
  datasetId: string,
): boolean {
  return Boolean(
    favorites?.favorites.some(
      (f) => f.project_id === projectId && f.dataset_id === datasetId && f.table_id === null,
    ),
  )
}

interface ToggleFavoriteVariables {
  projectId: string
  datasetId: string
  // null favorita/desfavorita o dataset inteiro.
  tableId: string | null
  isFavorite: boolean
}

interface ToggleFavoriteContext {
  previous: FavoritesListResponse | undefined
}

export function useToggleFavorite() {
  const queryClient = useQueryClient()

  return useMutation<Favorite | undefined, Error, ToggleFavoriteVariables, ToggleFavoriteContext>({
    mutationFn: ({ projectId, datasetId, tableId, isFavorite }: ToggleFavoriteVariables) => {
      if (isFavorite) {
        return tableId === null
          ? favoritesApi.removeDataset(projectId, datasetId)
          : favoritesApi.removeTable(projectId, datasetId, tableId)
      }
      return favoritesApi.add(projectId, datasetId, tableId)
    },

    // Otimista: a estrela muda antes da resposta da API chegar. Reverte
    // via context.previous se a chamada falhar.
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: FAVORITES_QUERY_KEY })
      const previous = queryClient.getQueryData<FavoritesListResponse>(FAVORITES_QUERY_KEY)

      queryClient.setQueryData<FavoritesListResponse>(FAVORITES_QUERY_KEY, (old) => {
        const current = old ?? { favorites: [] }
        if (variables.isFavorite) {
          return {
            favorites: current.favorites.filter(
              (f) =>
                !(
                  f.project_id === variables.projectId &&
                  f.dataset_id === variables.datasetId &&
                  f.table_id === variables.tableId
                ),
            ),
          }
        }
        return {
          favorites: [
            {
              project_id: variables.projectId,
              dataset_id: variables.datasetId,
              table_id: variables.tableId,
              nickname: null,
              added_at: new Date().toISOString(),
            },
            ...current.favorites,
          ],
        }
      })

      return { previous }
    },
    onError: (_err, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(FAVORITES_QUERY_KEY, context.previous)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: FAVORITES_QUERY_KEY })
    },
  })
}

interface UpdateFavoriteNicknameVariables {
  projectId: string
  datasetId: string
  tableId: string | null
  nickname: string
}

interface UpdateFavoriteNicknameContext {
  previous: FavoritesListResponse | undefined
}

export function useUpdateFavoriteNickname() {
  const queryClient = useQueryClient()

  return useMutation<
    Favorite,
    Error,
    UpdateFavoriteNicknameVariables,
    UpdateFavoriteNicknameContext
  >({
    mutationFn: ({ projectId, datasetId, tableId, nickname }: UpdateFavoriteNicknameVariables) =>
      favoritesApi.add(projectId, datasetId, tableId, nickname),

    // Otimista: troca só o nickname in-place, sem reordenar a lista local
    // (added_at é preservado no backend, então a ordem real também não muda).
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: FAVORITES_QUERY_KEY })
      const previous = queryClient.getQueryData<FavoritesListResponse>(FAVORITES_QUERY_KEY)

      queryClient.setQueryData<FavoritesListResponse>(FAVORITES_QUERY_KEY, (old) => {
        if (!old) return old
        return {
          favorites: old.favorites.map((f) =>
            f.project_id === variables.projectId &&
            f.dataset_id === variables.datasetId &&
            f.table_id === variables.tableId
              ? { ...f, nickname: variables.nickname || null }
              : f,
          ),
        }
      })

      return { previous }
    },
    onError: (_err, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(FAVORITES_QUERY_KEY, context.previous)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: FAVORITES_QUERY_KEY })
    },
  })
}
