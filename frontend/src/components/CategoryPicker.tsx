import { useState } from 'react';
import { CATEGORIES, CATEGORY_MAP } from '../api/categories';

interface Props {
  value: string;
  onChange: (category: string) => void;
}

/** Two-level category picker: top-level category → optional subcategory.
 *  Emits the subcategory value when selected, otherwise the top-level value.
 *  Emits empty string when cleared.
 */
export function CategoryPicker({ value, onChange }: Props) {
  // Derive initial top/sub from current value
  const initialTop = CATEGORIES.find((c) => c === value)
    ?? CATEGORIES.find((c) => CATEGORY_MAP[c]?.includes(value))
    ?? '';
  const initialSub = initialTop && CATEGORY_MAP[initialTop]?.includes(value) ? value : '';

  const [top, setTop] = useState(initialTop);
  const [sub, setSub] = useState(initialSub);

  const subcategories = top ? CATEGORY_MAP[top] ?? [] : [];

  function handleTopChange(newTop: string) {
    setTop(newTop);
    setSub('');
    onChange(newTop);
  }

  function handleSubChange(newSub: string) {
    setSub(newSub);
    onChange(newSub || top);
  }

  return (
    <div className="category-picker">
      <select
        value={top}
        onChange={(e) => handleTopChange(e.target.value)}
        className="filter-select"
        aria-label="Category"
      >
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>

      {subcategories.length > 0 && (
        <select
          value={sub}
          onChange={(e) => handleSubChange(e.target.value)}
          className="filter-select"
          aria-label="Subcategory"
        >
          <option value="">All {top}</option>
          {subcategories.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      )}
    </div>
  );
}
