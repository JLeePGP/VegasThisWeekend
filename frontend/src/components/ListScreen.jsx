import { useCallback, useEffect, useMemo, useRef } from 'react';
import { trackListEnd, trackSave } from '../analytics';
import { DEFAULT_FILTERS, DESKTOP_QUERY } from '../constants';
import { dayHeading, groupByDay } from '../format';
import useEvents from '../hooks/useEvents';
import useMediaQuery from '../hooks/useMediaQuery';
import { useSavedEvents } from '../store/savedEvents';
import EmailCapture from './EmailCapture';
import EmptyState from './EmptyState';
import EventRow from './EventRow';
import FilterBar from './FilterBar';
import FilterBarDesktop from './FilterBarDesktop';

// The listing. Every event matching the filters, grouped under the day it belongs to and
// in time order within each day.
//
// This replaced a swipe deck, and the reason is worth keeping next to the code: a weekend
// of events is a finite, time-ordered, comparable set. The question people actually have
// is "what else is on at 9pm?", and a card stack physically cannot answer it — one card
// at a time is the wrong shape for comparison. Nothing is dismissed, nothing is consumed,
// and coming back to the same screen shows the same events in the same places.

export default function ListScreen({ filters, onFiltersChange }) {
  const { status, items, total, hasMore, sampleData, error, loadMore, reload } = useEvents(filters);
  const { save, isSaved } = useSavedEvents();

  // The two filter bars take identical props and drive the same state in `App`. Only the
  // arrangement differs — a bottom sheet where space is scarce, labelled dropdowns where
  // it is not — so nothing below this line knows which one is mounted.
  const isDesktop = useMediaQuery(DESKTOP_QUERY);

  const days = useMemo(() => groupByDay(items), [items]);

  const handleSave = useCallback(
    (event) => {
      trackSave(event.id);
      save(event);
    },
    [save],
  );

  // Paging is driven by a sentinel at the foot of the list rather than by a scroll
  // handler: an observer fires once when the element comes into view, where a scroll
  // listener runs on every frame of every scroll to answer the same question.
  const sentinel = useRef(null);
  useEffect(() => {
    const element = sentinel.current;
    if (!element || !hasMore || status !== 'ready') return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore();
      },
      // Start the next page before the reader reaches the bottom, so the list grows
      // under them instead of stopping and then jumping.
      { rootMargin: '600px' },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [hasMore, status, loadMore]);

  // Reaching the end of the listing is a content signal, not a UI state: it means the
  // catalog ran out for the filters someone actually picked. It replaces the deck's
  // `stack_exhausted`, which was 31% of sessions and the clearest evidence that sourcing
  // — not layout — is the binding constraint. Fired once per filter set, not per render,
  // and only when the last page is really loaded.
  const reportedEnd = useRef(null);
  const filterKey = JSON.stringify(filters);
  useEffect(() => {
    if (status !== 'ready' || hasMore || items.length === 0) return;
    if (reportedEnd.current === filterKey) return;
    reportedEnd.current = filterKey;
    trackListEnd();
  }, [status, hasMore, items.length, filterKey]);

  const filtersAreNarrowed =
    filters.vibes.length > 0 ||
    filters.prices.length > 0 ||
    filters.alcoholFree ||
    filters.date !== DEFAULT_FILTERS.date;

  function renderList() {
    if (status === 'error') {
      return (
        <EmptyState icon="⚠" title="Couldn't load events" body={error}>
          <button type="button" className="btn btn--primary" onClick={reload}>
            Try again
          </button>
        </EmptyState>
      );
    }

    if (status === 'loading') {
      return <div className="skeleton" aria-label="Loading events" />;
    }

    if (total === 0) {
      return (
        <EmptyState
          icon="🌵"
          title="Nothing matches"
          body="No events fit those filters. Widen them and something will turn up."
        >
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => onFiltersChange({ ...DEFAULT_FILTERS, date: 'all' })}
          >
            Show anytime
          </button>
          {filtersAreNarrowed && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => onFiltersChange(DEFAULT_FILTERS)}
            >
              Reset filters
            </button>
          )}
        </EmptyState>
      );
    }

    return (
      <>
        {days.map(({ day, events }) => {
          const { lead, date } = dayHeading(day);
          return (
            <section className="day" key={day} aria-labelledby={`day-${day}`}>
              <h2 className="day__heading" id={`day-${day}`}>
                {lead && <span className="day__lead">{lead}</span>}
                <span className="day__date">{date}</span>
                <span className="day__count">
                  {events.length} {events.length === 1 ? 'event' : 'events'}
                </span>
              </h2>
              <ul className="list">
                {events.map((event) => (
                  <EventRow
                    key={event.id}
                    event={event}
                    onSave={handleSave}
                    isSaved={isSaved(event.id)}
                  />
                ))}
              </ul>
            </section>
          );
        })}

        {/* Watched by the observer above. Kept in the tree whether or not more pages
            exist, so the observer has something to attach to the moment one does. */}
        <div ref={sentinel} className="list__sentinel" aria-hidden="true" />

        {hasMore ? (
          <div className="skeleton skeleton--rows" aria-label="Loading more events" />
        ) : (
          <EmailCapture source="list_end" />
        )}
      </>
    );
  }

  return (
    <div className="screen">
      {sampleData && (
        <p className="banner">
          <strong>Sample data.</strong>&nbsp;These events and venues are invented placeholders
          for testing the app — none of them are real.
        </p>
      )}

      {isDesktop ? (
        <FilterBarDesktop filters={filters} onChange={onFiltersChange} />
      ) : (
        <FilterBar filters={filters} onChange={onFiltersChange} />
      )}

      {renderList()}
    </div>
  );
}
