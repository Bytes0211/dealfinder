import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { CATEGORIES } from '../api/categories';

interface Props {
  value: string[];
  onChange: (categories: string[]) => void;
  label?: string;
}

/** Multi-category tag input.
 *  Type and press Enter to add a custom category, or open the Browse panel
 *  to check/uncheck multiple predefined categories at once.
 */
export function CategoryTagInput({ value, onChange, label = 'Preferred Categories' }: Props) {
  const [input, setInput] = useState('');
  const [browseOpen, setBrowseOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close the panel when clicking outside
  useEffect(() => {
    if (!browseOpen) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setBrowseOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [browseOpen]);

  function addCategory(cat: string) {
    const trimmed = cat.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput('');
  }

  function removeCategory(cat: string) {
    onChange(value.filter((c) => c !== cat));
  }

  function toggleCategory(cat: string) {
    if (value.includes(cat)) {
      onChange(value.filter((c) => c !== cat));
    } else {
      onChange([...value, cat]);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      addCategory(input);
    } else if (e.key === 'Backspace' && input === '' && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  function handleChange(v: string) {
    setInput(v);
    if (CATEGORIES.includes(v)) {
      addCategory(v);
    }
  }

  return (
    <div className="form-label">
      {label}
      <div className="tag-input-wrap">
        {value.map((cat) => (
          <span key={cat} className="tag">
            {cat}
            <button
              type="button"
              className="tag-remove"
              onClick={() => removeCategory(cat)}
              aria-label={`Remove ${cat}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          list="pref-category-options"
          placeholder={value.length === 0 ? 'Search category…' : 'Add another…'}
          value={input}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className="tag-input"
        />
      </div>

      <div className="category-browse" ref={panelRef}>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => setBrowseOpen((o) => !o)}
          aria-expanded={browseOpen}
        >
          {browseOpen ? 'Close' : 'Browse all categories'}
        </button>

        {browseOpen && (
          <div className="category-browse__panel" role="group" aria-label="Category checkboxes">
            {CATEGORIES.map((cat) => (
              <label key={cat} className="category-browse__item">
                <input
                  type="checkbox"
                  checked={value.includes(cat)}
                  onChange={() => toggleCategory(cat)}
                />
                {cat}
              </label>
            ))}
          </div>
        )}
      </div>

      <datalist id="pref-category-options">
        {CATEGORIES.filter((c) => !value.includes(c)).map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      <span className="form-hint">Type and press Enter, or use Browse to select multiple.</span>
    </div>
  );
}
