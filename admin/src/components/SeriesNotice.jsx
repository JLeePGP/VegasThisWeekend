import { useState } from 'react';
import { linkSeries } from '../api';

/**
 * Shown above the edit form when the event being edited is one night of a run — or
 * could be.
 *
 * Two jobs, and they are the same job at different stages:
 *
 * **This is a series.** Say how many nights, when the next one is, and let the save reach
 * them. The scope choice defaults to this night alone every time, because the failure
 * mode here is not "had to edit twenty-six nights by hand" — it is "changed twenty-six
 * nights without meaning to", and only one of those is recoverable.
 *
 * **This could be a series.** Events entered before series ids existed have nothing
 * linking them, including a real three-night run in production. Matching nights are
 * listed with their dates and linked only when John says so. Nothing infers it: two
 * separate runs of an annual event look exactly like one residency to a query.
 */
export default function SeriesNotice({ eventId, series, scope, onScopeChange, onLinked }) {
  const [linking, setLinking] = useState(false);
  const [error, setError] = useState(null);

  if (!series) return null;

  const { series_id: seriesId, nights, future_count: futureCount, candidates } = series;

  if (!seriesId && candidates.length === 0) return null;

  async function link() {
    setLinking(true);
    setError(null);
    try {
      // The event being edited is the anchor; the candidates it was shown with are the
      // rest. Sending the ids back is what makes this John's decision and not a query's.
      onLinked(await linkSeries(eventId, candidates.map((night) => night.id)));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setLinking(false);
    }
  }

  if (!seriesId) {
    return (
      <div className="notice">
        <strong>
          {candidates.length} other {candidates.length === 1 ? 'night' : 'nights'} share
          this name and venue
        </strong>
        <p className="muted">
          {candidates.map((night) => night.starts_at_local.replace('T', ' ')).join(' · ')}
        </p>
        <p className="muted">
          Link them and one edit can change every later night at once. They stay separate
          rows either way — this only groups them.
        </p>
        {error && <p className="error">{error}</p>}
        <button type="button" className="btn btn--small" disabled={linking} onClick={link}>
          {linking ? 'Linking…' : 'Link these nights'}
        </button>
      </div>
    );
  }

  const next = nights.find((night) => !night.is_past);

  return (
    <div className="notice">
      <strong>
        One night of a {nights.length}-night run
        {next && ` · next on ${next.starts_at_local.replace('T', ' ')}`}
      </strong>

      <div className="chip-row" role="radiogroup" aria-label="What this edit changes">
        {[
          ['occurrence', 'Just this night'],
          [
            'series',
            futureCount > 0
              ? `This and ${futureCount} later ${futureCount === 1 ? 'night' : 'nights'}`
              : 'This and later nights',
          ],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={scope === value}
            className="chip"
            data-selected={scope === value}
            disabled={value === 'series' && futureCount === 0}
            onClick={() => onScopeChange(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <p className="muted">
        {scope === 'series'
          ? 'Details and the time of day apply to every later night. Each night keeps its own date, and nights already past are never touched.'
          : 'Only this night changes.'}
      </p>
    </div>
  );
}
