import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getDeal, listDeals, topDeals } from '../api/deals';
import { getUserPreferences, updatePreferences } from '../api/users';
import type { DealFilters, UserPreferencesUpdate } from '../api/types';

export function useDeals(filters: DealFilters = {}, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', filters],
    queryFn: () => listDeals(filters),
    enabled: options?.enabled,
  });
}

export function useTopDeals(limit = 20) {
  return useQuery({
    queryKey: ['deals', 'top', limit],
    queryFn: () => topDeals(limit),
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
    },
  });
}
