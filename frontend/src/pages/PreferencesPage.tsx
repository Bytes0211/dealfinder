import { useState, useEffect } from 'react';
import { getUserId } from '../auth';
import { useUpdatePreferences, useUserPreferences } from '../hooks';
import { CategoryTagInput } from '../components/CategoryTagInput';
import { InfoTooltip } from '../components/InfoTooltip';

export function PreferencesPage() {
  const userId = getUserId() ?? '';
  const { data: existing } = useUserPreferences(userId);
  const { mutate, isPending, isSuccess, isError } = useUpdatePreferences(userId);

  const [discountThreshold, setDiscountThreshold] = useState('');
  const [categories, setCategories] = useState<string[]>([]);
  const [pushoverKey, setPushoverKey] = useState('');

  // Seed form fields once existing preferences are loaded
  useEffect(() => {
    if (!existing) return;
    if (existing.discount_threshold != null) {
      setDiscountThreshold(String(existing.discount_threshold));
    }
    if (existing.preferred_categories?.length) {
      setCategories(existing.preferred_categories as string[]);
    }
    if (existing.pushover_user_key) {
      setPushoverKey(existing.pushover_user_key);
    }
  }, [existing]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutate({
      discount_threshold: discountThreshold || null,
      preferred_categories: categories.length > 0 ? categories : null,
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

        <CategoryTagInput value={categories} onChange={setCategories} />

        <label className="form-label">
          <span className="form-label-row">
            Pushover User Key
            <InfoTooltip text="Your personal Pushover User Key, found on your dashboard at pushover.net. The app uses it to send deal alerts directly to your phone or device via the Pushover app." />
          </span>
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
