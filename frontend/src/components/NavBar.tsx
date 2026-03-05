import { Link, useLocation } from 'react-router-dom';
import { isAuthenticated, login, logout } from '../auth';

export function NavBar() {
  const { pathname } = useLocation();
  const authed = isAuthenticated();

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">🔍 Deal Finder</Link>
      <div className="navbar-links">
        <Link to="/" className={pathname === '/' ? 'active' : ''}>Feed</Link>
        <Link to="/top" className={pathname === '/top' ? 'active' : ''}>Top Deals</Link>
        {authed && (
          <Link to="/preferences" className={pathname === '/preferences' ? 'active' : ''}>
            Preferences
          </Link>
        )}
      </div>
      <div className="navbar-auth">
        {authed ? (
          <button onClick={logout} className="btn btn-outline">Log out</button>
        ) : (
          <button onClick={login} className="btn btn-primary">Log in</button>
        )}
      </div>
    </nav>
  );
}
