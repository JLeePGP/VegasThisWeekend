import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackDetailOpen, trackSave, trackSkip, trackStackExhausted } from '../analytics';
import { DEFAULT_FILTERS } from '../constants';
import useEvents from '../hooks/useEvents';
import { useSavedEvents } from '../store/savedEvents';
import EmptyState from './EmptyState';
import EventSheet from './EventSheet';
import FilterBar from './FilterBar';
import { IconChevronUp, IconSave, IconSkip } from './Icons';
import SwipeStack from './SwipeStack';

// Fetch the next page while there are still this many cards left to swipe.
const PREFETCH_AT = 5;

const prefersTouch =
  typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches;

export default function DiscoverScreen({ filters, onFiltersChange }) {
  const navigate = useNavigate();
  const { status, items, total, hasMore, sampleData, error, loadMore, reload } = useEvents(filters);
  const { savedIds, dismissedIds, save, dismiss, resetDismissed, dismissedCount, isSaved } =
    useSavedEvents();

  const [detail, setDetail] = useState(null);
  const controls = useRef(null);

  // Anything already saved or dismissed is gone from the stack. Deriving the queue rather
  // than mutating it means a save and a dismiss need no separate bookkeeping.
  const queue = useMemo(
    () => items.filter((event) => !savedIds.has(event.id) && !dismissedIds.has(event.id)),
    [items, savedIds, dismissedIds],
  );

  useEffect(() => {
    if (status === 'ready' && hasMore && queue.length < PREFETCH_AT) loadMore();
  }, [status, hasMore, queue.length, loadMore]);

  const handleSave = useCallback(
    (event, method) => {
      trackSave(event.id);
      save(event);
    },
    [save],
  );

  const handleDismiss = useCallback(
    (event, method) => {
      trackSkip(event.id);
      dismiss(event.id);
    },
    [dismiss],
  );

  const openDetail = useCallback((event) => {
    trackDetailOpen(event.id);
    setDetail(event);
  }, []);

  // Running out of cards is a content signal, not just a UI state — a high rate means
  // the catalog is too thin for the filters people are actually using. Fired once per
  // exhaustion rather than on every render.
  const alreadyReportedEmpty = useRef(false);
  useEffect(() => {
    if (queue.length > 0) {
      alreadyReportedEmpty.current = false;
      return;
    }
    if (status !== 'ready' || hasMore || total === 0) return;
    if (!alreadyReportedEmpty.current) {
      alreadyReportedEmpty.current = true;
      trackStackExhausted();
    }
  }, [queue.length, status, hasMore, total]);

  const filtersAreNarrowed =
    filters.vibes.length > 0 || filters.prices.length > 0 || filters.date !== DEFAULT_FILTERS.date;

  function renderStack() {
    if (status === 'error') {
      return (
        <EmptyState icon="⚠" title="Couldn't load events" body={error}>
          <button type="button" className="btn btn--primary" onClick={reload}>
            Try again
          </button>
        </EmptyState>
      );
    }

    // Still loading, or draining the last cards while the next page is in flight.
    if (status === 'loading' || (queue.length === 0 && hasMore)) {
      return <div className="skeleton" aria-label="Loading events" />;
    }

    if (queue.length === 0) {
      return total === 0 ? (
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
      ) : (
        <EmptyState
          icon="✦"
          title="That's everything"
          body="You've been through every event matching these filters."
        >
          <button type="button" className="btn btn--primary" onClick={() => navigate('/saved')}>
            See what you saved
          </button>
          {dismissedCount > 0 && (
            <button type="button" className="btn btn--ghost" onClick={resetDismissed}>
              Start over
            </button>
          )}
        </EmptyState>
      );
    }

    return (
      <SwipeStack
        events={queue}
        controlsRef={controls}
        onSave={handleSave}
        onDismiss={handleDismiss}
        onExpand={openDetail}
        inputLocked={detail !== null}
      />
    );
  }

  const top = queue[0] ?? null;

  return (
    <>
      {sampleData && (
        <p className="banner">
          <strong>Sample data.</strong>&nbsp;These events and venues are invented placeholders
          for testing the app — none of them are real.
        </p>
      )}

      {/* The media layer. Absolutely positioned across the whole shell so a card reaches
          the edges of the screen; every control below floats over it. Kept as a sibling
          of the chrome rather than a parent so the chrome's stacking order stays obvious. */}
      <div className="stage">{renderStack()}</div>

      <FilterBar filters={filters} onChange={onFiltersChange} />

      {/* Transparent spacer that pins the controls to the bottom. It must not swallow
          pointer events, or the lower half of the card would stop being swipeable — the
          controls themselves opt back in. */}
      <div className="discover">
        <div className="actions">
          <button
            type="button"
            className="action action--skip"
            onClick={() => controls.current?.skip()}
            disabled={!top}
            aria-label="Skip this event"
          >
            <IconSkip width={26} height={26} />
          </button>
          <button
            type="button"
            className="action action--details"
            onClick={() => top && openDetail(top)}
            disabled={!top}
            aria-label="Show details"
          >
            <IconChevronUp width={20} height={20} />
          </button>
          <button
            type="button"
            className="action action--save"
            onClick={() => controls.current?.save()}
            disabled={!top}
            aria-label="Save this event"
          >
            <IconSave width={26} height={26} />
          </button>
        </div>

        <p className="hint">
          {prefersTouch
            ? 'Swipe right to save · left to skip'
            : 'Use ← and → to decide · ↑ for details'}
        </p>
      </div>

      <EventSheet
        event={detail}
        open={detail !== null}
        onClose={() => setDetail(null)}
        onSave={save}
        isSaved={detail ? isSaved(detail.id) : false}
      />
    </>
  );
}
