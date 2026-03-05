import { useEffect } from 'react';
import { isAuthenticated, login } from '../auth';
import { useNavigate } from 'react-router-dom';

export function LoginPage() {
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated()) {
      navigate('/', { replace: true });
    }
  }, [navigate]);

  return (
    <div className="page page--centered">
      <h1>🔍 Deal Finder</h1>
      <p className="page-subtitle">Sign in to manage your notification preferences.</p>
      <button onClick={login} className="btn btn-primary btn-lg">
        Sign in with Cognito
      </button>
      <p className="hint">Deal browsing is available without signing in.</p>
    </div>
  );
}
