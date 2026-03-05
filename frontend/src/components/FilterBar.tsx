import { CategoryPicker } from './CategoryPicker';

interface Props {
  /** Currently committed (active) category value. */
  category: string;
  /** Currently committed (active) status value. */
  status: string;
  /** Whether a search has been run (controls save icon visibility). */
  hasSearched: boolean;
  /** Whether the save icon should show as already saved. */
  isSaved: boolean;
  onCategoryChange: (v: string) => void;
  onStatusChange: (v: string) => void;
  onSearch: () => void;
  onSave: () => void;
  onReset: () => void;
}

const STATUSES = ['', 'discovered', 'evaluating', 'evaluated', 'notified', 'expired', 'rejected'];

export function FilterBar({
  category, status, hasSearched, isSaved,
  onCategoryChange, onStatusChange, onSearch, onSave, onReset,
}: Props) {
  return (
    <div className="filter-bar">
      <CategoryPicker value={category} onChange={onCategoryChange} />

      <select
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
        className="filter-select"
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>{s || 'All statuses'}</option>
        ))}
      </select>

      <button
        onClick={onSearch}
        disabled={!category}
        className="btn btn-primary btn-sm"
        title={!category ? 'Select a category to search' : 'Search deals'}
      >
        🔍 Search
      </button>

      {hasSearched && (
        <button
          onClick={onSave}
          className={`btn btn-sm ${isSaved ? 'btn-saved' : 'btn-outline'}`}
          title={isSaved ? 'Feed saved' : 'Save this feed'}
        >
          {isSaved ? '🔖 Saved' : '🔖 Save feed'}
        </button>
      )}

      {(category || status) && (
        <button onClick={onReset} className="btn btn-outline btn-sm">Clear</button>
      )}
    </div>
  );
}
