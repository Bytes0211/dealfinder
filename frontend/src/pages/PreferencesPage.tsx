import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { getUserId, logout } from '../auth';
import { useUpdatePreferences, useUserPreferences, useDeleteUser } from '../hooks';

/** Validate E.164 phone number format: +[country code][number], 7–15 digits. */
function isValidE164(phone: string) {
  return /^\+[1-9]\d{6,14}$/.test(phone);
}

export function PreferencesPage() {
  const navigate = useNavigate();
  const userId = getUserId() ?? '';
  const { data: existing } = useUserPreferences(userId);
  const { mutate, isPending, isSuccess, isError, error: prefsError } = useUpdatePreferences(userId);
  const { mutate: doDelete, isPending: isDeleting } = useDeleteUser(userId);

  const [phoneNumber, setPhoneNumber] = useState('');
  const [phoneError, setPhoneError] = useState('');
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteMsg, setDeleteMsg] = useState('');

  // Seed form from loaded preferences
  useEffect(() => {
    if (!existing) return;
    if (existing.phone_number) setPhoneNumber(existing.phone_number);
    setEmailEnabled(existing.notification_preferences?.email === true);
  }, [existing]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPhoneError('');
    const phone = phoneNumber.trim();
    if (phone && !isValidE164(phone)) {
      setPhoneError('Enter a valid E.164 number, e.g. +12125551234');
      return;
    }
    mutate({
      phone_number: phone || null,
      notification_preferences: { email: emailEnabled },
    });
  }

  function handleDeleteAccount() {
    doDelete(undefined, {
      onSuccess: () => {
        setDeleteMsg('Your account has been deactivated.');
        logout();
        navigate('/login');
      },
      onError: () => setDeleteMsg('Failed to deactivate account. Please try again.'),
    });
  }

  return (
    <div className="page page--narrow">
      <h1>Preferences</h1>
      <p className="page-subtitle">Manage your notification channels and account settings.</p>

      {/* ──── Email Notifications */}
      <section className="pref-section">
        <h2>Email Notifications</h2>
        <p className="section-subtitle">
          Deal alerts and watchlist updates will be sent to{' '}
          <strong>{existing?.email ?? 'your account email'}</strong>.
        </p>
        <label className="form-label" style={{ flexDirection: 'row', alignItems: 'center', gap: '.6rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={emailEnabled}
            onChange={(e) => setEmailEnabled(e.target.checked)}
          />
          Enable email notifications
        </label>
      </section>

      {/* ──── Phone Notifications */}
      <section className="pref-section">
        <h2>SMS Notifications</h2>
        <p className="section-subtitle">
          Add your phone number to receive SMS deal alerts via SNS. Use E.164 format, e.g.{' '}
          <code>+12125551234</code>. Leave blank to disable.
        </p>
        <form onSubmit={handleSubmit} className="pref-form">
          <label className="form-label">
            Phone number
            <input
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="+12125551234"
              className="form-input"
            />
          </label>
          {phoneError && <p className="form-feedback form-feedback--error">{phoneError}</p>}

          <button type="submit" disabled={isPending} className="btn btn-primary">
            {isPending ? 'Saving…' : 'Save'}
          </button>

          {isSuccess && <p className="form-feedback form-feedback--ok">✓ Preferences saved.</p>}
          {isError && (
            <p className="form-feedback form-feedback--error">
              Failed to save:{' '}
              {(() => {
                console.error('[PreferencesPage] save error:', prefsError);
                if (isAxiosError(prefsError) && prefsError.response) {
                  const d = prefsError.response.data;
                  return d?.detail
                    ? String(d.detail)
                    : `HTTP ${prefsError.response.status}: ${JSON.stringify(d)}`;
                }
                if (isAxiosError(prefsError)) {
                  return `Network error: ${prefsError.message}`;
                }
                return String(prefsError);
              })()}
            </p>
          )}
        </form>
      </section>

      {/* ──── Danger Zone */}
      <section className="pref-section pref-section--danger">
        <h2>Account</h2>
        {!confirmDelete ? (
          <>
            <p>Deactivating your account will stop all deal alerts. This cannot be undone.</p>
            <button
              onClick={() => setConfirmDelete(true)}
              className="btn btn-danger"
            >
              Deactivate Account
            </button>
          </>
        ) : (
          <>
            <p className="form-feedback form-feedback--error">
              Are you sure? This will deactivate your account immediately.
            </p>
            <div className="btn-group">
              <button
                onClick={handleDeleteAccount}
                disabled={isDeleting}
                className="btn btn-danger"
              >
                {isDeleting ? 'Deactivating…' : 'Yes, deactivate my account'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="btn btn-outline"
              >
                Cancel
              </button>
            </div>
            {deleteMsg && (
              <p className={`form-feedback ${deleteMsg.startsWith('Failed') ? 'form-feedback--error' : 'form-feedback--ok'}`}>
                {deleteMsg}
              </p>
            )}
          </>
        )}
      </section>
    </div>
  );
}
