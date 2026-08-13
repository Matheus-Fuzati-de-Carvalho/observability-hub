import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { favoritesApi } from '@/lib/api/favorites'
import type { FavoritesListResponse, FavoriteTable } from '@/types/favorites'

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

interface ToggleFavoriteVariables {
  projectId: string
  datasetId: string
  tableId: string
  isFavorite: boolean
}

interface ToggleFavoriteContext {
  previous: FavoritesListResponse | undefined
}

export function useToggleFavorite() {
  const queryClient = useQueryClient()

  return useMutation<
    FavoriteTable | undefined,
    Error,
    ToggleFavoriteVariables,
    ToggleFavoriteContext
  >({
    mutationFn: ({ projectId, datasetId, tableId, isFavorite }: ToggleFavoriteVariables) =>
      isFavorite
        ? favoritesApi.remove(projectId, datasetId, tableId)
        : favoritesApi.add(projectId, datasetId, tableId),

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
