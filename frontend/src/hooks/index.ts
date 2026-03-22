import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getDeal, listDeals, topDeals } from '../api/deals';
import { postSearch } from '../api/search';
import { deleteUser, getUserPreferences, getWatchlistMatches, updatePreferences } from '../api/users';
import type { DealFilters, SearchRequest, UserPreferencesUpdate } from '../api/types';

export function useDeals(filters: DealFilters = {}, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', filters],
    queryFn: () => listDeals(filters),
    enabled: options?.enabled,
  });
}

export function useTopDeals(limit = 20, minDiscount?: number) {
  return useQuery({
    queryKey: ['deals', 'top', limit, minDiscount],
    queryFn: () => topDeals(limit, minDiscount),
  });
}

export function useDeal(id: string) {
  return useQuery({
    queryKey: ['deals', id],
    queryFn: () => getDeal(id),
    enabled: !!id,
  });
}

export function useUserPreferences(userId: string) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: () => getUserPreferences(userId),
    enabled: !!userId,
    staleTime: 60_000, // cache for 1 minute
  });
}

export function useUpdatePreferences(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UserPreferencesUpdate) => updatePreferences(userId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', userId] });
      queryClient.invalidateQueries({ queryKey: ['watchlist-matches', userId] });
      // Removing a watchlist feed deletes orphaned deals on the backend,
      // so top deals and the main deals list must be refreshed.
      queryClient.invalidateQueries({ queryKey: ['deals'] });
    },
  });
}

export function useSearch() {
  return useMutation({
    mutationFn: (body: SearchRequest) => postSearch(body),
  });
}

export function useDeleteUser(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => deleteUser(userId),
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

export function useWatchlistMatches(
  userId: string,
  limit = 20,
  offset = 0,
  enabled = true,
) {
  return useQuery({
    queryKey: ['watchlist-matches', userId, limit, offset],
    queryFn: () => getWatchlistMatches(userId, limit, offset),
    enabled: enabled && !!userId,
    staleTime: 30_000,
  });
}
