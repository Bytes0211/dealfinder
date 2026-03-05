interface Props {
  category: string;
  status: string;
  onCategoryChange: (v: string) => void;
  onStatusChange: (v: string) => void;
  onReset: () => void;
}

const STATUSES = ['', 'new', 'evaluated', 'notified', 'archived'];

export function FilterBar({ category, status, onCategoryChange, onStatusChange, onReset }: Props) {
  return (
    <div className="filter-bar">
      <input
        type="text"
        placeholder="Filter by category…"
        value={category}
        onChange={(e) => onCategoryChange(e.target.value)}
        className="filter-input"
      />
      <select
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
        className="filter-select"
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>{s || 'All statuses'}</option>
        ))}
      </select>
      {(category || status) && (
        <button onClick={onReset} className="btn btn-outline btn-sm">Clear</button>
      )}
    </div>
  );
}
