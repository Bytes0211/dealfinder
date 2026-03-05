import { DealCard } from '../components/DealCard';
import { useTopDeals } from '../hooks';

export function TopDealsPage() {
  const { data, isLoading, isError } = useTopDeals(20);

  return (
    <div className="page">
      <h1>🔥 Top Deals</h1>
      <p className="page-subtitle">High-value deals sorted by discount percentage</p>

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
