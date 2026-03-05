interface Props {
  offset: number;
  limit: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ offset, limit, total, onPrev, onNext }: Props) {
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  if (totalPages <= 1) return null;

  return (
    <div className="pagination">
      <button onClick={onPrev} disabled={offset === 0} className="btn btn-outline btn-sm">
        ← Prev
      </button>
      <span className="pagination-info">
        Page {page} of {totalPages} &nbsp;·&nbsp; {total} deals
      </span>
      <button
        onClick={onNext}
        disabled={offset + limit >= total}
        className="btn btn-outline btn-sm"
      >
        Next →
      </button>
    </div>
  );
}
