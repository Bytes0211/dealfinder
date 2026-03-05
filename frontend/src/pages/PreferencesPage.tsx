import { useState } from 'react';
import { getUserId } from '../auth';
import { useUpdatePreferences } from '../hooks';

export function PreferencesPage() {
  const userId = getUserId() ?? '';
  const { mutate, isPending, isSuccess, isError } = useUpdatePreferences(userId);

  const [discountThreshold, setDiscountThreshold] = useState('');
  const [categories, setCategories] = useState('');
  const [pushoverKey, setPushoverKey] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutate({
      discount_threshold: discountThreshold || null,
      preferred_categories: categories
        ? categories.split(',').map((s) => s.trim()).filter(Boolean)
        : null,
      pushover_user_key: pushoverKey || null,
    });
  }

  return (
    <div className="page page--narrow">
      <h1>Notification Preferences</h1>
      <p className="page-subtitle">Configure how and when you receive deal alerts.</p>

      <form onSubmit={handleSubmit} className="pref-form">
        <label className="form-label">
          Minimum Discount (%)
          <input
            type="number"
            min="0"
            max="100"
            step="1"
            value={discountThreshold}
            onChange={(e) => setDiscountThreshold(e.target.value)}
            placeholder="e.g. 30"
            className="form-input"
          />
        </label>

        <label className="form-label">
          Preferred Categories (comma-separated)
          <input
            type="text"
            value={categories}
            onChange={(e) => setCategories(e.target.value)}
            placeholder="e.g. Electronics, Clothing"
            className="form-input"
          />
        </label>

        <label className="form-label">
          Pushover User Key
          <input
            type="text"
            value={pushoverKey}
            onChange={(e) => setPushoverKey(e.target.value)}
            placeholder="Your Pushover user key"
            className="form-input"
          />
        </label>

        <button type="submit" disabled={isPending} className="btn btn-primary">
          {isPending ? 'Saving…' : 'Save Preferences'}
        </button>

        {isSuccess && <p className="form-feedback form-feedback--ok">✓ Preferences saved.</p>}
        {isError && (
          <p className="form-feedback form-feedback--error">
            Failed to save. Are you logged in?
          </p>
        )}
      </form>
    </div>
  );
}
