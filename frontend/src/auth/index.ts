import { authConfig } from './config';

const TOKEN_KEY = 'dealfinder_access_token';
const USER_ID_KEY = 'dealfinder_user_id';

/** Redirect to Cognito Hosted UI login page (implicit flow). */
export function login(): void {
  const params = new URLSearchParams({
    client_id: authConfig.clientId,
    response_type: 'token',
    scope: authConfig.scope,
    redirect_uri: authConfig.redirectUri,
  });
  window.location.href = `https://${authConfig.cognitoDomain}/login?${params}`;
}

/** Clear session and redirect to Cognito logout endpoint. */
export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_ID_KEY);
  const params = new URLSearchParams({
    client_id: authConfig.clientId,
    logout_uri: window.location.origin,
  });
  window.location.href = `https://${authConfig.cognitoDomain}/logout?${params}`;
}

/**
 * Parse access_token from the URL fragment after Cognito redirect.
 * Returns true if a token was found and stored.
 */
export function handleCallback(): boolean {
  const hash = window.location.hash.substring(1);
  const params = new URLSearchParams(hash);
  const token = params.get('access_token');
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    return true;
  }
  return false;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

export function setUserId(id: string): void {
  localStorage.setItem(USER_ID_KEY, id);
}

export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}
