import { useCallback, useEffect, useState } from 'react';
import { deactivateEvent, listEvents } from '../api';

export default function EventList({ onEdit, refreshKey }) {
  const [events, setEvents] = useState([]);
  const [query, setQuery] = useState('');
  const [includeInactive, setIncludeInactive] = useState(true);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);

  const load = useCallback(async (q, inactive) => {
    setStatus('loading');
    setError(null);
    try {
      setEvents(await listEvents({ q, includeInactive: inactive }));
      setStatus('ready');
    } catch (failure) {
      setError(failure.message);
      setStatus('error');
    }
  }, []);

  // Debounced so typing a venue name is not one request per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => load(query, includeInactive), 250);
    return () => window.clearTimeout(timer);
  }, [query, includeInactive, refreshKey, load]);

  async function pull(event) {
    if (!window.confirm(`Pull "${event.name}" from the app? It stays in the database.`)) return;
    try {
      await deactivateEvent(event.id);
      load(query, includeInactive);
    } catch (failure) {
      setError(failure.message);
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <h2>Events</h2>
        <p>{events.length} shown, soonest first</p>
        <label className="checkbox spacer">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(changed) => setIncludeInactive(changed.target.checked)}
          />
          <span>Include inactive</span>
        </label>
      </div>

      <div className="field" style={{ marginBottom: 14 }}>
        <label htmlFor="event-search">Search name or venue</label>
        <input
          id="event-search"
          type="text"
          value={query}
          onChange={(changed) => setQuery(changed.target.value)}
          placeholder="neon cathedral"
        />
      </div>

      {error && (
        <div className="banner" data-tone="error">
          {error}
        </div>
      )}

      {status === 'loading' && <div className="empty">Loading…</div>}

      {status === 'ready' && events.length === 0 && (
        <div className="empty">
          {query ? `Nothing matches "${query}".` : 'No events yet. Add one from the first tab.'}
        </div>
      )}

      {status === 'ready' && events.length > 0 && (
        <div className="rows">
          <div className="row row--head">
            <span className="row__when">Starts (Vegas)</span>
            <span className="row__main">Event</span>
            <span className="row__tag">Category</span>
            <span className="row__buttons" style={{ width: 140 }} />
          </div>

          {events.map((event) => (
            <div className="row" key={event.id} data-inactive={!event.is_active}>
              <span className="row__when">{event.starts_at_local.replace('T', ' ')}</span>
              <div className="row__main">
                <div className="row__title">
                  {event.name}
                  {event.is_sample && ' · sample'}
                </div>
                <div className="row__sub">
                  {event.venue} · {event.neighborhood}
                </div>
              </div>
              <span className="row__tag">{event.vibe}</span>
              <div className="row__buttons">
                <button type="button" className="btn btn--ghost btn--small" onClick={() => onEdit(event)}>
                  Edit
                </button>
                {event.is_active && (
                  <button type="button" className="btn btn--danger btn--small" onClick={() => pull(event)}>
                    Pull
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
