import { useState } from 'react';
import { Link } from 'react-router-dom';
import { DealCard } from '../components/DealCard';
import { Pagination } from '../components/Pagination';
import { useUserPreferences, useUpdatePreferences, useWatchlistMatches } from '../hooks';
import { isAuthenticated, getUserId, login } from '../auth';
import type { SavedFeed, DealResponse } from '../api/types';

const PAGE_SIZE = 20;

/** Quality badge — mirrors SearchPage display for consistency in the feed. */
function QualityBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  if (score >= 8) return <span className="quality-badge quality-badge--great">🟢 Great</span>;
  if (score >= 5) return <span className="quality-badge quality-badge--fair">🟡 Fair</span>;
  return <span className="quality-badge quality-badge--weak">🔴 Weak</span>;
}

/** Trend badge — shows demand direction with confidence for WatchlistAgent deals. */
function TrendBadge({ trend, confidence }: { trend: string | null; confidence: number | null }) {
  if (!trend) return null;
  const icon = trend === 'upward' ? '↑' : trend === 'downward' ? '↓' : '→';
  const cls = trend === 'upward' ? 'trend-badge--up' : trend === 'downward' ? 'trend-badge--down' : 'trend-badge--stable';
  const label = trend.charAt(0).toUpperCase() + trend.slice(1);
  const pct = confidence != null ? ` ${Math.round(confidence * 100)}%` : '';
  return <span className={`trend-badge ${cls}`}>{icon} {label}{pct}</span>;
}

/** Compact trend signals row */
function TrendSignals({ deal }: { deal: DealResponse }) {
  if (!deal.trend) return null;
  const parts: string[] = [];
  if (deal.price_trend) parts.push(`Price: ${deal.price_trend}`);
  if (deal.discount_frequency) parts.push(`Discounts: ${deal.discount_frequency}`);
  if (deal.review_velocity) parts.push(`Reviews: ${deal.review_velocity}`);
  if (deal.competitor_activity) parts.push(`Competitors: ${deal.competitor_activity}`);
  return (
    <div className="trend-signals">
      <TrendBadge trend={deal.trend} confidence={deal.trend_confidence} />
      {parts.length > 0 && <span className="trend-signals-text">{parts.join(' · ')}</span>}
    </div>
  );
}

export function FeedPage() {
  const authed = isAuthenticated();
  const userId = getUserId() ?? '';

  // Watchlist edits
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDiscount, setEditDiscount] = useState<number>(20);

  // Matched deals pagination
  const [matchOffset, setMatchOffset] = useState(0);

  // Per-feed filter — null means show all
  const [activeFeedId, setActiveFeedId] = useState<string | null>(null);

  function toggleFeedFilter(feedId: string) {
    setActiveFeedId((prev) => (prev === feedId ? null : feedId));
    setMatchOffset(0);
  }

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
    if (activeFeedId === feed.id) setActiveFeedId(null);
    savePrefs({ saved_feeds: updated });
  }

  // Client-side filter — mirrors the backend ILIKE keyword logic
  const activeFeed = savedFeeds.find((f) => f.id === activeFeedId) ?? null;
  const visibleDeals = activeFeed && matchData
    ? matchData.items.filter((deal) => {
        const keywords = activeFeed.query.toLowerCase().split(' ').filter((w) => w.length > 2).slice(0, 3);
        return keywords.some((kw) => deal.title.toLowerCase().includes(kw));
      })
    : (matchData?.items ?? []);

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
      <section className="feed-section feed-watchlist-col">
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
                      <button
                        onClick={() => toggleFeedFilter(feed.id)}
                        className={`btn btn-sm ${
                          activeFeedId === feed.id ? 'btn-filter-active' : 'btn-filter'
                        }`}
                        title={activeFeedId === feed.id ? 'Clear filter' : 'Filter deals to this item'}
                      >
                        {activeFeedId === feed.id ? '⊗ Filtered' : '⊕ Filter'}
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
          <div className="feed-section-header">
            <h2>Matched Deals</h2>
            {activeFeed && (
              <span className="feed-filter-pill">
                {activeFeed.title}
                <button onClick={() => setActiveFeedId(null)} className="feed-filter-pill-clear" title="Clear filter">×</button>
              </span>
            )}
          </div>
          <p className="section-subtitle">
            {activeFeed
              ? `Showing deals for "${activeFeed.query}"`
              : 'Deals discovered for your watchlist queries, enriched with Bedrock trend analysis.'}
          </p>

          {matchLoading && <p className="state-msg state-msg--left">Loading matches…</p>}
          {matchError && (
            <p className="state-msg state-msg--left state-msg--error">Could not load matched deals.</p>
          )}
          {matchData && (
            <>
              {matchData.items.length === 0 ? (
                <p className="state-msg state-msg--left">
                  No matched deals yet.{matchData.last_scan_at ? (
                    <>{' '}Last scan: {new Date(matchData.last_scan_at).toLocaleString()}{matchData.sources_scanned != null && matchData.sources_scanned > 0 && (
                      <> &mdash; {matchData.sources_scanned} source{matchData.sources_scanned !== 1 ? 's' : ''} scanned</>)}</>
                  ) : ' Check back after the next pipeline run.'}
                </p>
              ) : (
                <>
                  <p className="result-count">
                    {activeFeed ? `${visibleDeals.length} of ${matchData.total}` : matchData.total} matched deals
                  </p>
                <div className="deal-grid">
                    {visibleDeals.map((deal) => (
                      <div key={deal.id} className="match-card">
                        <DealCard deal={deal} />
                        {deal.trend && (
                          <div className="match-card-trend">
                            <TrendSignals deal={deal} />
                            {deal.trend_summary && (
                              <p className="trend-summary">{deal.trend_summary}</p>
                            )}
                          </div>
                        )}
                      </div>
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
