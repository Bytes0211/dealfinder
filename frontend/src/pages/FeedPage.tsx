import { useState } from 'react';
import { DealCard } from '../components/DealCard';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { useDeals } from '../hooks';

const PAGE_SIZE = 20;

export function FeedPage() {
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);

  const { data, isLoading, isError } = useDeals({
    category: category || undefined,
    status: status || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  function handleReset() {
    setCategory('');
    setStatus('');
    setOffset(0);
  }

  return (
    <div className="page">
      <h1>Deal Feed</h1>
      <FilterBar
        category={category}
        status={status}
        onCategoryChange={(v) => { setCategory(v); setOffset(0); }}
        onStatusChange={(v) => { setStatus(v); setOffset(0); }}
        onReset={handleReset}
      />

      {isLoading && <p className="state-msg">Loading deals…</p>}
      {isError && <p className="state-msg state-msg--error">Failed to load deals. Is the API running?</p>}

      {data && (
        <>
          <p className="result-count">{data.total} deals found</p>
          <div className="deal-grid">
            {data.items.map((deal) => (
              <DealCard key={deal.id} deal={deal} />
            ))}
          </div>
          {data.items.length === 0 && !isLoading && (
            <p className="state-msg">No deals match your filters.</p>
          )}
          <Pagination
            offset={offset}
            limit={PAGE_SIZE}
            total={data.total}
            onPrev={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            onNext={() => setOffset((o) => o + PAGE_SIZE)}
          />
        </>
      )}
    </div>
  );
}
