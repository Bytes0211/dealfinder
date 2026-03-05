import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getDeal, listDeals, topDeals } from '../api/deals';
import { updatePreferences } from '../api/users';
import type { DealFilters, UserPreferencesUpdate } from '../api/types';

export function useDeals(filters: DealFilters = {}) {
  return useQuery({
    queryKey: ['deals', filters],
    queryFn: () => listDeals(filters),
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

export function useUpdatePreferences(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UserPreferencesUpdate) => updatePreferences(userId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', userId] });
    },
  });
}
