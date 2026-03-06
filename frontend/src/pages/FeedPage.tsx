import { useState } from 'react';
import { Link } from 'react-router-dom';
import { DealCard } from '../components/DealCard';
import { Pagination } from '../components/Pagination';
import { useUserPreferences, useUpdatePreferences, useWatchlistMatches } from '../hooks';
import { isAuthenticated, getUserId, login } from '../auth';
import type { SavedFeed } from '../api/types';

const PAGE_SIZE = 20;

/** Quality badge — mirrors SearchPage display for consistency in the feed. */
function QualityBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  if (score >= 8) return <span className="quality-badge quality-badge--great">🟢 Great</span>;
  if (score >= 5) return <span className="quality-badge quality-badge--fair">🟡 Fair</span>;
  return <span className="quality-badge quality-badge--weak">🔴 Weak</span>;
}

export function FeedPage() {
  const authed = isAuthenticated();
  const userId = getUserId() ?? '';

  // Watchlist edits
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDiscount, setEditDiscount] = useState<number>(20);

  // Matched deals pagination
  const [matchOffset, setMatchOffset] = useState(0);

  const { data: userPrefs } = useUserPreferences(authed ? userId : '');
  const { mutate: savePrefs } = useUpdatePreferences(userId);

  const savedFeeds: SavedFeed[] =
    ((userPrefs?.notification_preferences?.saved_feeds as SavedFeed[] | undefined) ?? [])
      .filter((f) => f.id && f.title && f.url);

  const {
    data: matchData,
    isLoading: matchLoading,
    isError: matchError,
  } = useWatchlistMatches(userId, PAGE_SIZE, matchOffset, authed && savedFeeds.length > 0);

  // ── Watchlist helpers ──────────────────────────────────────

  function startEdit(feed: SavedFeed) {
    setEditingId(feed.id);
    setEditDiscount(feed.min_discount);
  }

  function commitEdit(feed: SavedFeed) {
    const updated = savedFeeds.map((f) =>
      f.id === feed.id ? { ...f, min_discount: editDiscount } : f,
    );
    savePrefs({ saved_feeds: updated });
    setEditingId(null);
  }

  function removeFeed(feed: SavedFeed) {
    const updated = savedFeeds.filter((f) => f.id !== feed.id);
    savePrefs({ saved_feeds: updated });
  }

  // ── Render ───────────────────────────────────────────

  if (!authed) {
    return (
      <div className="page page--centered">
        <p className="state-msg">Log in to see your watchlist and deal matches.</p>
        <button onClick={login} className="btn btn-primary">Log in</button>
      </div>
    );
  }

  return (
    <div className="page">
      {/* ──────────── Section A: Watchlist ──────────── */}
      <section className="feed-section">
        <div className="feed-section-header">
          <h2>My Watchlist</h2>
          <Link to="/search" className="btn btn-outline btn-sm">+ New Search</Link>
        </div>

        {savedFeeds.length === 0 ? (
          <p className="state-msg">
            No saved feeds yet.{' '}
            <Link to="/search">Search for a deal</Link> and save it to start watching.
          </p>
        ) : (
          <div className="watchlist-list">
            {savedFeeds.map((feed) => (
              <div key={feed.id} className="watchlist-card">
                <div className="watchlist-card-main">
                  <a
                    href={feed.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="watchlist-card-title"
                  >
                    {feed.title}
                  </a>
                  <div className="watchlist-card-meta">
                    {feed.current_price && (
                      <span className="watchlist-card-price">{feed.current_price}</span>
                    )}
                    <QualityBadge score={feed.quality_score} />
                  </div>
                </div>

                <div className="watchlist-card-actions">
                  {editingId === feed.id ? (
                    <>
                      <label className="watchlist-discount-edit">
                        <span>Min&nbsp;%</span>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={editDiscount}
                          onChange={(e) => setEditDiscount(Number(e.target.value))}
                          className="form-input form-input--sm"
                        />
                      </label>
                      <button
                        onClick={() => commitEdit(feed)}
                        className="btn btn-primary btn-sm"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="btn btn-outline btn-sm"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="watchlist-discount-badge">
                        ≥{feed.min_discount}%&nbsp;off
                      </span>
                      <button
                        onClick={() => startEdit(feed)}
                        className="btn btn-outline btn-sm"
                      >
                        Edit
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => removeFeed(feed)}
                    className="btn btn-danger btn-sm"
                    aria-label="Remove from watchlist"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ──────────── Section B: Matched Deals ──────────── */}
      {savedFeeds.length > 0 && (
        <section className="feed-section">
          <h2>Matched Deals</h2>
          <p className="section-subtitle">
            RSS deals from your feeds that meet your minimum discount thresholds.
          </p>

          {matchLoading && <p className="state-msg">Loading matches…</p>}
          {matchError && (
            <p className="state-msg state-msg--error">Could not load matched deals.</p>
          )}
          {matchData && (
            <>
              {matchData.items.length === 0 ? (
                <p className="state-msg">No matched deals yet. Check back after the next pipeline run.</p>
              ) : (
                <>
                  <p className="result-count">{matchData.total} matched deals</p>
                  <div className="deal-grid">
                    {matchData.items.map((deal) => (
                      <DealCard key={deal.id} deal={deal} />
                    ))}
                  </div>
                  <Pagination
                    offset={matchOffset}
                    limit={PAGE_SIZE}
                    total={matchData.total}
                    onPrev={() => setMatchOffset((o) => Math.max(0, o - PAGE_SIZE))}
                    onNext={() => setMatchOffset((o) => o + PAGE_SIZE)}
                  />
                </>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}
