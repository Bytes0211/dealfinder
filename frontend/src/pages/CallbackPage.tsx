import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { handleCallback } from '../auth';

export function CallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const ok = handleCallback();
    navigate(ok ? '/' : '/login', { replace: true });
  }, [navigate]);

  return (
    <div className="page page--centered">
      <p className="state-msg">Signing you in…</p>
    </div>
  );
}
