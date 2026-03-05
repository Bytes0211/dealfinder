import { apiClient } from './client';
import type { UserPreferencesUpdate, UserResponse } from './types';

/** PUT /api/v1/users/:id/preferences — update notification preferences. Requires auth. */
export async function updatePreferences(
  userId: string,
  body: UserPreferencesUpdate,
): Promise<UserResponse> {
  const { data } = await apiClient.put<UserResponse>(`/users/${userId}/preferences`, body);
  return data;
}
