import { apiClient } from './client';
import type { DealListResponse, UserPreferencesUpdate, UserResponse } from './types';

/** GET /api/v1/users/:id — fetch user profile and preferences. Requires auth. */
export async function getUserPreferences(userId: string): Promise<UserResponse> {
  const { data } = await apiClient.get<UserResponse>(`/users/${userId}`);
  return data;
}

/** PUT /api/v1/users/:id/preferences — update notification preferences. Requires auth. */
export async function updatePreferences(
  userId: string,
  body: UserPreferencesUpdate,
): Promise<UserResponse> {
  const { data } = await apiClient.put<UserResponse>(`/users/${userId}/preferences`, body);
  return data;
}

/**
 * DELETE /api/v1/users/:id — deactivate the user account (sets is_active=false).
 * Requires auth.
 */
export async function deleteUser(userId: string): Promise<void> {
  await apiClient.delete(`/users/${userId}`);
}

/**
 * GET /api/v1/users/:id/watchlist/matches — paginated list of RSS deals that
 * match at least one of the user's saved feed queries. Requires auth.
 */
export async function getWatchlistMatches(
  userId: string,
  limit = 20,
  offset = 0,
): Promise<DealListResponse> {
  const { data } = await apiClient.get<DealListResponse>(
    `/users/${userId}/watchlist/matches`,
    { params: { limit, offset } },
  );
  return data;
}
