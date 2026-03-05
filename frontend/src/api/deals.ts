import { apiClient } from './client';
import type { DealFilters, DealListResponse, DealResponse } from './types';

/** GET /api/v1/deals — paginated list with optional filters. */
export async function listDeals(filters: DealFilters = {}): Promise<DealListResponse> {
  const { data } = await apiClient.get<DealListResponse>('/deals', { params: filters });
  return data;
}

/** GET /api/v1/deals/top — high-value deals sorted by discount. */
export async function topDeals(limit = 20): Promise<DealResponse[]> {
  const { data } = await apiClient.get<DealResponse[]>('/deals/top', { params: { limit } });
  return data;
}

/** GET /api/v1/deals/:id — single deal detail. */
export async function getDeal(id: string): Promise<DealResponse> {
  const { data } = await apiClient.get<DealResponse>(`/deals/${id}`);
  return data;
}
