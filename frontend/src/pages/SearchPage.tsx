import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { useSearch, useUpdatePreferences, useUserPreferences } from '../hooks';
import { isAuthenticated, getUserId } from '../auth';
import type { SavedFeed, SearchResult } from '../api/types';

/** Returns a quality badge emoji + label based on the 0–10 score. */
function QualityBadge({ score }: { score: number }) {
  if (score >= 8) {
    return <span className="quality-badge quality-badge--great">🟢 Great Deal</span>;
  }
  if (score >= 5) {
    return <span className="quality-badge quality-badge--fair">🟡 Fair</span>;
  }
  return <span className="quality-badge quality-badge--weak">🔴 Weak</span>;
}

/** State tracked per search result row. */
interface ResultState {
  selected: boolean;
  minDiscount: number;
}

export function SearchPage() {
  const navigate = useNavigate();
  const authed = isAuthenticated();
  const userId = getUserId() ?? '';

  const [query, setQuery] = useState('');
  const [resultStates, setResultStates] = useState<Record<number, ResultState>>({});
  const [savedIndexes, setSavedIndexes] = useState<Set<number>>(new Set());
  const [saveMsg, setSaveMsg] = useState('');

  const {
    mutate: search,
    data: searchData,
    isPending: isSearching,
    isError: searchError,
    error: searchErrorObj,
  } = useSearch();

  const searchErrorMsg = searchErrorObj
    ? isAxiosError(searchErrorObj) && searchErrorObj.response?.data?.detail
      ? String(searchErrorObj.response.data.detail)
      : 'An unexpected error occurred — please try again.'
    : '';

  const { data: userPrefs } = useUserPreferences(authed ? userId : '');
  const { mutate: savePrefs } = useUpdatePreferences(userId);

  const results: SearchResult[] = searchData?.results ?? [];

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setResultStates({});
    setSavedIndexes(new Set());
    setSaveMsg('');
    search({ query: query.trim() });
  }

  function toggleSelect(i: number) {
    setResultStates((prev) => ({
      ...prev,
      [i]: {
        selected: !prev[i]?.selected,
        minDiscount: prev[i]?.minDiscount ?? 20,
      },
    }));
  }

  function setMinDiscount(i: number, value: number) {
    setResultStates((prev) => ({
      ...prev,
      [i]: { ...prev[i], selected: prev[i]?.selected ?? false, minDiscount: value },
    }));
  }

  function handleSaveSelected() {
    if (!authed) {
      setSaveMsg('Log in to save feeds.');
      return;
    }
    const selected = results
      .map((r, i) => ({ r, i }))
      .filter(({ i }) => resultStates[i]?.selected && !savedIndexes.has(i));

    if (selected.length === 0) {
      setSaveMsg('Select at least one result to save.');
      return;
    }

    const existing: SavedFeed[] =
      ((userPrefs?.notification_preferences?.saved_feeds as SavedFeed[] | undefined) ?? []);

    const newFeeds: SavedFeed[] = selected.map(({ r, i }) => ({
      id: crypto.randomUUID(),
      query: searchData?.query ?? query.trim(),
      title: r.title,
      url: r.url,
      current_price: r.current_price,
      min_discount: resultStates[i]?.minDiscount ?? 20,
      quality_score: r.quality_score,
      quality_reason: r.quality_reason,
      saved_at: new Date().toISOString(),
    }));

    savePrefs(
      { saved_feeds: [...existing, ...newFeeds] },
      {
        onSuccess: () => {
          setSavedIndexes((prev) => new Set([...prev, ...selected.map(({ i }) => i)]));
          setSaveMsg(`${newFeeds.length} feed${newFeeds.length !== 1 ? 's' : ''} saved ✔`);
        },
        onError: () => setSaveMsg('Failed to save. Are you logged in?'),
      },
    );
  }

  const anySelected = results.some((_, i) => resultStates[i]?.selected && !savedIndexes.has(i));

  return (
    <div className="page">
      <h1>Search for Deals</h1>
      <p className="page-subtitle">
        Describe what you're looking for. Powered by Bedrock (Claude) and Tavily.
      </p>

      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. Sony noise-cancelling headphones"
          className="search-input"
          disabled={isSearching}
        />
        <button type="submit" disabled={isSearching || !query.trim()} className="btn btn-primary">
          {isSearching ? 'Searching…' : 'Search'}
        </button>
      </form>

      {searchError && (
        <p className="state-msg state-msg--error">Search failed: {searchErrorMsg}</p>
      )}

      {results.length > 0 && (
        <>
          <p className="result-count">{results.length} results for "{searchData?.query}"</p>

          <div className="search-results">
            {results.map((result, i) => {
              const state = resultStates[i] ?? { selected: false, minDiscount: 20 };
              const isSaved = savedIndexes.has(i);
              return (
                <div
                  key={i}
                  className={`search-result-card${state.selected ? ' search-result-card--selected' : ''}${isSaved ? ' search-result-card--saved' : ''}`}
                >
                  <label className="search-result-check">
                    <input
                      type="checkbox"
                      checked={state.selected}
                      disabled={isSaved}
                      onChange={() => toggleSelect(i)}
                    />
                  </label>

                  <div className="search-result-body">
                    <a
                      href={result.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="search-result-title"
                    >
                      {result.title}
                    </a>
                    <div className="search-result-meta">
                      {result.current_price && (
                        <span className="search-result-price">{result.current_price}</span>
                      )}
                      <QualityBadge score={result.quality_score} />
                      {result.quality_reason && (
                        <span className="search-result-reason">{result.quality_reason}</span>
                      )}
                    </div>
                  </div>

                  {state.selected && !isSaved && (
                    <label className="search-result-discount">
                      <span>Min&nbsp;discount&nbsp;%</span>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        step={1}
                        value={state.minDiscount}
                        onChange={(e) => setMinDiscount(i, Number(e.target.value))}
                        className="form-input form-input--sm"
                      />
                    </label>
                  )}

                  {isSaved && <span className="badge badge--ok">Saved ✔</span>}
                </div>
              );
            })}
          </div>

          <div className="search-actions">
            {authed && (
              <button
                onClick={handleSaveSelected}
                disabled={!anySelected}
                className="btn btn-primary"
              >
                Save selected to watchlist
              </button>
            )}
            <button
              onClick={() => navigate('/')}
              className="btn btn-outline"
            >
              View my watchlist
            </button>
          </div>

          {saveMsg && (
            <p
              className={`state-msg ${saveMsg.startsWith('Failed') || saveMsg.startsWith('Log') || saveMsg.startsWith('Select') ? 'state-msg--error' : 'state-msg--ok'}`}
            >
              {saveMsg}
            </p>
          )}
        </>
      )}

      {searchData && results.length === 0 && !isSearching && (
        <p className="state-msg">No results found. Try a different search term.</p>
      )}
    </div>
  );
}
