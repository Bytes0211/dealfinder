import { Link } from 'react-router-dom';
import { DealCard } from '../components/DealCard';
import { useTopDeals, useUserPreferences } from '../hooks';
import { isAuthenticated, getUserId } from '../auth';

export function TopDealsPage() {
  const authed = isAuthenticated();
  const userId = getUserId() ?? '';
  const { data: userPrefs, isLoading: prefsLoading } = useUserPreferences(authed ? userId : '');

  const minDiscount = typeof userPrefs?.notification_preferences?.min_discount_percentage === 'number'
    ? (userPrefs.notification_preferences.min_discount_percentage as number)
    : undefined;

  const { data, isLoading, isError } = useTopDeals(20, minDiscount, {
    enabled: !authed || !prefsLoading,
  });

  return (
    <div className="page">
      <h1>🔥 Top Deals</h1>
      <p className="page-subtitle">
        High-value deals sorted by discount percentage
        {minDiscount != null && minDiscount > 0 && (
          <> &mdash; filtered to ≥{minDiscount}% off.{' '}
            <Link to="/preferences">Change</Link>
          </>
        )}
      </p>

      {isLoading && <p className="state-msg">Loading…</p>}
      {isError && <p className="state-msg state-msg--error">Failed to load top deals.</p>}

      {data && (
        <div className="deal-grid">
          {data.map((deal) => (
            <DealCard key={deal.id} deal={deal} />
          ))}
          {data.length === 0 && <p className="state-msg">No high-value deals found yet.</p>}
        </div>
      )}
    </div>
  );
}
