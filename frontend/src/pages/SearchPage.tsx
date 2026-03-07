import { useEffect, useState } from 'react';
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
}

export function SearchPage() {
  const navigate = useNavigate();
  const authed = isAuthenticated();
  const userId = getUserId() ?? '';

  const [query, setQuery] = useState('');
  const [resultStates, setResultStates] = useState<Record<number, ResultState>>({});
  const [savedIndexes, setSavedIndexes] = useState<Set<number>>(new Set());
  const [saveMsg, setSaveMsg] = useState('');
  const [modelName, setModelName] = useState<string | null>(null);

  useEffect(() => {
    fetch('/config/bedrock_models.json')
      .then((r) => r.json())
      .then((data) => setModelName(data.search_extractor ?? data.default ?? null))
      .catch(() => setModelName(null));
  }, []);

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
      },
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
      ((userPrefs?.notification_preferences?.saved_feeds as SavedFeed[] | undefined) ?? [])
        .filter((f) => f.id && f.title && f.url);

    const newFeeds: SavedFeed[] = selected.map(({ r }) => ({
      id: crypto.randomUUID(),
      query: searchData?.query ?? query.trim(),
      title: r.title,
      url: r.url,
      current_price: r.current_price,
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
        onError: (err) => {
          console.error('[SearchPage] save error:', err);
          let detail: string;
          if (isAxiosError(err) && err.response) {
            const d = err.response.data;
            if (d?.detail) {
              if (Array.isArray(d.detail)) {
                // FastAPI 422 validation errors — format each entry as "field: message"
                detail = (d.detail as Array<{ loc?: string[]; msg?: string }>)
                  .map((e) => {
                    const field = (e.loc ?? []).slice(1).join('.') || 'field';
                    return `${field}: ${e.msg ?? 'invalid'}`;
                  })
                  .join('; ');
              } else {
                detail = String(d.detail);
              }
            } else {
              detail = `HTTP ${err.response.status}: ${JSON.stringify(d)}`;
            }
          } else if (isAxiosError(err)) {
            detail = `Network error: ${err.message}`;
          } else {
            detail = String(err);
          }
          setSaveMsg(`Failed to save: ${detail}`);
        },
      },
    );
  }

  const anySelected = results.some((_, i) => resultStates[i]?.selected && !savedIndexes.has(i));

  return (
    <div className="page">
      <h1>Search for Deals</h1>
      <p className="page-subtitle">
        Describe what you're looking for — an agentic AI-powered search
        {modelName ? ` using ${modelName}.` : '.'}
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

          <table className="search-table">
            <thead>
              <tr>
                <th></th>
                <th>Feed</th>
                <th>Description</th>
                <th>Quality Score</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {results.map((result, i) => {
                const state = resultStates[i] ?? { selected: false };
                const isSaved = savedIndexes.has(i);
                return (
                  <tr
                    key={i}
                    className={`search-row${state.selected ? ' search-row--selected' : ''}${isSaved ? ' search-row--saved' : ''}`}
                  >
                    <td className="search-row-check">
                      <input
                        type="checkbox"
                        checked={state.selected}
                        disabled={isSaved}
                        onChange={() => toggleSelect(i)}
                      />
                    </td>

                    <td className="search-row-feed">
                      <a href={result.url} target="_blank" rel="noopener noreferrer">
                        {result.title}
                      </a>
                    </td>

                    <td className="search-row-desc">
                      {result.current_price && (
                        <span className="search-result-price">{result.current_price}</span>
                      )}
                      {result.quality_reason && (
                        <span className="search-result-reason">{result.quality_reason}</span>
                      )}
                    </td>

                    <td className="search-row-quality">
                      <QualityBadge score={result.quality_score} />
                    </td>

                    <td className="search-row-actions">
                      {isSaved && <span className="badge badge--ok">Saved ✔</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

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
