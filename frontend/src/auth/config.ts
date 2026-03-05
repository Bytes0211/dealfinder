/** Cognito Hosted UI configuration loaded from environment variables. */
export const authConfig = {
  /** e.g. dealfinder-dev.auth.us-east-1.amazoncognito.com */
  cognitoDomain: import.meta.env.VITE_COGNITO_DOMAIN ?? '',
  clientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? '',
  redirectUri:
    import.meta.env.VITE_COGNITO_REDIRECT_URI ??
    `${window.location.origin}/auth/callback`,
  scope: 'openid email profile',
};
