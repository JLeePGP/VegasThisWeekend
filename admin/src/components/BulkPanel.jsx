import { useCallback, useEffect, useState } from 'react';
import { discardExtraction, listExtractions, submitExtractions } from '../api';

// Paste a block of URLs, one per line, and come back to a queue of drafts.
//
// The queue lives on the server rather than in this component's state, because the
// Batch API is asynchronous — a batch can take the best part of an hour, so the tab has
// to be closable, and John wanted to keep adding URLs to a run already in flight.

const STATUS_LABELS = {
  queued: 'Queued',
  running: 'Extracting…',
  ready: 'Ready to review',
  failed: 'Failed',
  approved: 'Saved',
};

// Only while something is still in flight. A queue of finished drafts should sit still.
const POLL_MS = 20000;

export default function BulkPanel({ onReview, refreshKey }) {
  const [urls, setUrls] = useState('');
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async ({ refresh = true } = {}) => {
    try {
      setItems(await listExtractions({ refresh }));
      setError(null);
    } catch (err) {
      setError(err.message ?? 'Could not load the queue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const working = items.some((item) => item.status === 'running' || item.status === 'queued');

  useEffect(() => {
    if (!working) return undefined;
    const timer = window.setInterval(() => load(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [working, load]);

  const lineCount = urls.split('\n').filter((line) => line.trim()).length;

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await submitExtractions(urls);
      setUrls('');
      const parts = [`${result.queued} URL${result.queued === 1 ? '' : 's'} queued.`];
      if (result.rejected.length) {
        parts.push(`Skipped ${result.rejected.length}: ${result.rejected.join(', ')}`);
      }
      setNotice(parts.join(' '));
      await load({ refresh: false });
    } catch (err) {
      setError(err.message ?? 'Could not submit those URLs.');
    } finally {
      setBusy(false);
    }
  }

  async function handleDiscard(id) {
    try {
      await discardExtraction(id);
      setItems((current) => current.filter((item) => item.id !== id));
    } catch (err) {
      setError(err.message ?? 'Could not discard that draft.');
    }
  }

  return (
    <div className="bulk">
      <section className="panel">
        <div className="panel__head">
          <h2>Extract from a list of links</h2>
          <p>One URL per line. Nothing saves until you review it.</p>
        </div>

        <textarea
          className="bulk__input"
          rows={7}
          value={urls}
          onChange={(event) => setUrls(event.target.value)}
          placeholder={
            'https://www.eventbrite.com/e/...\nhttps://venue.example.com/events/friday\nhttps://www.tickettailor.com/events/...'
          }
        />

        <div className="bulk__actions">
          <button
            type="button"
            className="primary"
            onClick={handleSubmit}
            disabled={busy || lineCount === 0}
          >
            {busy ? 'Submitting…' : `Extract ${lineCount || ''} ${lineCount === 1 ? 'link' : 'links'}`.trim()}
          </button>
          <span className="bulk__hint">
            Batched, so it runs in the background — usually a few minutes. You can close
            this tab, and add more links while it works.
          </span>
        </div>

        {/* Said plainly rather than discovered by watching every Instagram link fail. */}
        <p className="bulk__caveat">
          Instagram and TikTok links will not work — those pages need a login, so no
          server can read them. Paste the caption into <strong>Add event</strong> instead.
          Pages that build themselves in the browser (vegas.com is one) usually fail too.
        </p>

        {notice && <p className="bulk__notice">{notice}</p>}
        {error && <p className="error">{error}</p>}
      </section>

      <section className="panel">
        <div className="panel__head">
          <h2>Queue</h2>
          <p>{working ? 'Refreshing while extraction runs.' : `${items.length} in the list.`}</p>
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : items.length === 0 ? (
          <p className="muted">Nothing queued. Paste some links above.</p>
        ) : (
          <ul className="queue">
            {items.map((item) => {
              const draft = item.draft?.draft;
              return (
                <li key={item.id} className="queue__row" data-status={item.status}>
                  <div className="queue__main">
                    <span className="queue__status" data-status={item.status}>
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                    <strong className="queue__title">
                      {draft ? draft.name : item.url}
                    </strong>
                    {draft && (
                      <span className="queue__meta">
                        {draft.venue} · {draft.starts_at_local.replace('T', ' ')}
                      </span>
                    )}
                    <a
                      className="queue__url"
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {item.url}
                    </a>
                    {item.error && <span className="queue__error">{item.error}</span>}
                    {item.looks_recurring && (
                      // Flagged, never acted on. A wrong recurrence guess in bulk would
                      // add dozens of events to delete one at a time.
                      <span className="queue__flag">
                        Looks like a series — check the repeat settings when you review it
                      </span>
                    )}
                  </div>

                  <div className="queue__buttons">
                    {item.status === 'ready' && (
                      <button
                        type="button"
                        className="primary"
                        onClick={() => onReview(item)}
                      >
                        Review
                      </button>
                    )}
                    {item.status !== 'approved' && (
                      <button type="button" onClick={() => handleDiscard(item.id)}>
                        Discard
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
