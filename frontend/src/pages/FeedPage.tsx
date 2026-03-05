import { useState, useEffect, useCallback } from 'react';
import { DealCard } from '../components/DealCard';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { useDeals, useUserPreferences, useUpdatePreferences } from '../hooks';
import { isAuthenticated, getUserId } from '../auth';
import { login } from '../auth';
import type { SavedFeed } from '../api/types';

const PAGE_SIZE = 20;

export function FeedPage() {
  const authed = isAuthenticated();
  const userId = getUserId() ?? '';

  // Pending (selected but not yet searched)
  const [pendingCategory, setPendingCategory] = useState('');
  const [pendingStatus, setPendingStatus] = useState('');

  // Active (committed — what the query uses)
  const [activeCategory, setActiveCategory] = useState('');
  const [activeStatus, setActiveStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);
  const [savedFeedMsg, setSavedFeedMsg] = useState('');

  // User preferences (for saved feeds panel)
  const { data: userPrefs } = useUserPreferences(authed ? userId : '');
  const { mutate: savePrefs } = useUpdatePreferences(userId);

  const savedFeeds: SavedFeed[] =
    (userPrefs?.notification_preferences?.saved_feeds as SavedFeed[] | undefined) ?? [];

  // Auto-load first saved feed on mount when authenticated
  useEffect(() => {
    if (authed && savedFeeds.length > 0 && !hasSearched) {
      const first = savedFeeds[0];
      setPendingCategory(first.category);
      setPendingStatus(first.status);
      setActiveCategory(first.category);
      setActiveStatus(first.status);
      setHasSearched(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userPrefs]);

  const { data, isLoading, isError } = useDeals(
    { category: activeCategory || undefined, status: activeStatus || undefined, limit: PAGE_SIZE, offset },
    { enabled: hasSearched },
  );

  function handleSearch() {
    setActiveCategory(pendingCategory);
    setActiveStatus(pendingStatus);
    setOffset(0);
    setHasSearched(true);
    setSavedFeedMsg('');
  }

  function handleReset() {
    setPendingCategory('');
    setPendingStatus('');
    setActiveCategory('');
    setActiveStatus('');
    setOffset(0);
    setHasSearched(false);
    setSavedFeedMsg('');
  }

  const isSaved = savedFeeds.some(
    (f) => f.category === activeCategory && f.status === activeStatus
  );

  function handleSave() {
    if (!authed) {
      setSavedFeedMsg('Log in to save feeds.');
      return;
    }
    if (isSaved) return;
    const updated: SavedFeed[] = [...savedFeeds, { category: activeCategory, status: activeStatus }];
    savePrefs({ saved_feeds: updated }, {
      onSuccess: () => setSavedFeedMsg('Feed saved ✔'),
      onError: () => setSavedFeedMsg('Failed to save feed.'),
    });
  }

  const handleDeleteFeed = useCallback((feed: SavedFeed) => {
    const updated = savedFeeds.filter(
      (f) => !(f.category === feed.category && f.status === feed.status)
    );
    savePrefs({ saved_feeds: updated });
  }, [savedFeeds, savePrefs]);

  // ── Render ──────────────────────────────────────────────────

  return (
    <div className="page">
      <h1>Deal Feed</h1>

      <FilterBar
        category={pendingCategory}
        status={pendingStatus}
        hasSearched={hasSearched}
        isSaved={isSaved}
        onCategoryChange={setPendingCategory}
        onStatusChange={setPendingStatus}
        onSearch={handleSearch}
        onSave={handleSave}
        onReset={handleReset}
      />
      {savedFeedMsg && (
        <p className={`state-msg ${savedFeedMsg.startsWith('Failed') || savedFeedMsg.startsWith('Log') ? 'state-msg--error' : 'state-msg--ok'}`}>
          {savedFeedMsg}
        </p>
      )}

      {/* Saved feeds panel */}
      {authed && savedFeeds.length > 0 && (
        <div className="saved-feeds-panel">
          <span className="saved-feeds-label">My feeds:</span>
          {savedFeeds.map((feed) => (
            <span
              key={`${feed.category}|${feed.status}`}
              className={`saved-feed-card ${
                feed.category === activeCategory && feed.status === activeStatus
                  ? 'saved-feed-card--active' : ''
              }`}
            >
              <button
                className="saved-feed-card-btn"
                onClick={() => {
                  setPendingCategory(feed.category);
                  setPendingStatus(feed.status);
                  setActiveCategory(feed.category);
                  setActiveStatus(feed.status);
                  setOffset(0);
                  setHasSearched(true);
                  setSavedFeedMsg('');
                }}
              >
                {feed.category}{feed.status ? ` · ${feed.status}` : ''}
              </button>
              <button
                className="saved-feed-delete"
                onClick={() => handleDeleteFeed(feed)}
                aria-label="Remove feed"
              >×</button>
            </span>
          ))}
        </div>
      )}

      {/* Empty states */}
      {!authed && !hasSearched && (
        <div className="page page--centered">
          <p className="state-msg">Log in to see your saved deal feed.</p>
          <button onClick={login} className="btn btn-primary">Log in</button>
        </div>
      )}
      {authed && !hasSearched && savedFeeds.length === 0 && (
        <p className="state-msg">
          Your account has no saved feeds. Use the search above to find deals and save your feed.
        </p>
      )}

      {/* Results */}
      {hasSearched && (
        <>
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
        </>
      )}
    </div>
  );
}
