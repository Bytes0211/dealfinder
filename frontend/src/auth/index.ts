import { authConfig } from './config';

const TOKEN_KEY = 'dealfinder_access_token';
const USER_ID_KEY = 'dealfinder_user_id';

/**
 * Decode a JWT payload without verifying the signature.
 * Safe for extracting claims like sub and exp on the client side.
 */
function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
  } catch {
    return {};
  }
}

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
 * Extracts the Cognito sub claim and stores it as the local userId.
 * Returns true if a token was found and stored.
 */
export function handleCallback(): boolean {
  const hash = window.location.hash.substring(1);
  const params = new URLSearchParams(hash);
  const token = params.get('access_token');
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    // Extract Cognito sub (user ID) from the access token payload
    const payload = decodeJwtPayload(token);
    const sub = payload.sub as string | undefined;
    if (sub) {
      localStorage.setItem(USER_ID_KEY, sub);
    }
    return true;
  }
  return false;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Returns true if a non-expired access token is present.
 * Clears stale tokens automatically.
 */
export function isAuthenticated(): boolean {
  const token = getAccessToken();
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  const exp = payload.exp as number | undefined;
  if (exp && Date.now() / 1000 > exp) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_ID_KEY);
    return false;
  }
  return true;
}

export function setUserId(id: string): void {
  localStorage.setItem(USER_ID_KEY, id);
}

export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}
