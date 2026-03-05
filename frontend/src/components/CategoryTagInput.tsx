import { useState, type KeyboardEvent } from 'react';
import { CATEGORIES } from '../api/categories';

interface Props {
  value: string[];
  onChange: (categories: string[]) => void;
  label?: string;
}

/** Multi-category tag input with datalist suggestions.
 *  Type to search, press Enter or Tab to add, click × to remove a tag.
 */
export function CategoryTagInput({ value, onChange, label = 'Preferred Categories' }: Props) {
  const [input, setInput] = useState('');

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

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      addCategory(input);
    } else if (e.key === 'Backspace' && input === '' && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  // Also fire when user picks from the datalist (input change to exact match)
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
      <datalist id="pref-category-options">
        {CATEGORIES.filter((c) => !value.includes(c)).map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      <span className="form-hint">Select from the list or type your own. Press Enter to add.</span>
    </div>
  );
}
