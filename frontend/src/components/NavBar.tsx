import { Link, useLocation } from 'react-router-dom';
import { isAuthenticated, login, logout } from '../auth';

export function NavBar() {
  const { pathname } = useLocation();
  const authed = isAuthenticated();

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        <svg className="navbar-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8 8a2 2 0 0 0 2.828 0l7.172-7.172a2 2 0 0 0 0-2.828l-8-8z" stroke="#0d6efd" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="7" cy="7" r="1.5" fill="#0d6efd"/>
        </svg>
        Deal Finder
      </Link>
      <div className="navbar-links">
        <Link to="/" className={pathname === '/' ? 'active' : ''}>Matched Deals</Link>
        <Link to="/search" className={pathname === '/search' ? 'active' : ''}>Search</Link>
        <Link to="/top" className={pathname === '/top' ? 'active' : ''}>Top Deals</Link>
        {authed ? (
          <>
            <Link to="/preferences" className={pathname === '/preferences' ? 'active' : ''}>
              Preferences
            </Link>
            <button onClick={logout} className="btn btn-outline btn-sm">Log out</button>
          </>
        ) : (
          <button onClick={login} className="btn btn-primary btn-sm">Log in</button>
        )}
      </div>
    </nav>
  );
}
