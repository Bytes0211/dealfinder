import { apiClient } from './client';
import type { UserPreferencesUpdate, UserResponse } from './types';

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
