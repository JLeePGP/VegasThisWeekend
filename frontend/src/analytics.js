// First-party interaction counting.
//
// Replaces Plausible. The reason is not cost: a cookieless pageview tool structurally
// cannot answer the question this app actually has — *which events* are people saving —
// because answering it means attaching a count to an event id, and sending event ids to
// a third party is exactly what we had decided not to do. Counting them ourselves is
// both more useful and more private: the server stores counters and nothing else, with
// no session, no IP and no user agent (see backend/app/models.py StatCounter).
//
// Two rules this file exists to enforce:
//
//   1. Analytics can never break the app. Every path is wrapped; a blocked request, an
//      offline device or a 500 is a silent no-op, never an exception mid-swipe.
//   2. Nothing identifying is ever sent. The payload is a list of {metric, event_id}
//      and there is no third field to add one to.

import { recordInteractions } from './api';

// Swiping produces a burst of interactions, so they are batched rather than sent one
// request per gesture. Flushed on whichever comes first.
const FLUSH_AFTER_MS = 8000;
const FLUSH_AT_COUNT = 20;
// Matches the server's per-request ceiling.
const MAX_BATCH = 50;

let queue = [];
let timer = null;

function flush() {
  if (timer) {
    window.clearTimeout(timer);
    timer = null;
  }
  if (queue.length === 0) return;

  const batch = queue.slice(0, MAX_BATCH);
  queue = queue.slice(MAX_BATCH);

  try {
    // keepalive so a flush triggered by the page going away still completes. Unlike
    // sendBeacon this can send application/json without tripping a CORS preflight it
    // cannot satisfy, and it reports failures we can swallow deliberately.
    recordInteractions(batch);
  } catch {
    // Dropped on purpose. Losing a few counts is not worth a broken interaction, and
    // retrying risks double-counting, which is worse than undercounting for a metric
    // whose entire job is comparing events against each other.
  }

  // A queue longer than one batch keeps draining.
  if (queue.length > 0) schedule();
}

function schedule() {
  if (timer) return;
  timer = window.setTimeout(flush, FLUSH_AFTER_MS);
}

function push(metric, eventId) {
  try {
    queue.push(eventId ? { metric, event_id: eventId } : { metric });
    if (queue.length >= FLUSH_AT_COUNT) flush();
    else schedule();
  } catch {
    // Nothing here can be allowed to surface.
  }
}

if (typeof window !== 'undefined') {
  // pagehide rather than unload: it fires on mobile Safari when the tab is backgrounded,
  // which is how most sessions on this app actually end.
  window.addEventListener('pagehide', flush);
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush();
  });
}

// --- per-event -------------------------------------------------------------------

/** Swiped right, or saved from the detail sheet. */
export const trackSave = (eventId) => push('save', eventId);

/** Swiped left. Paired with saves this gives a save rate, which is the number that
 *  ranks events honestly — raw saves just rank by time spent near the top of the stack. */
export const trackSkip = (eventId) => push('skip', eventId);

/** Opened the details. Depth of interest past the swipe. */
export const trackDetailOpen = (eventId) => push('detail_open', eventId);

/** Revealed an insider tip. Says whether curating them is worth the effort. */
export const trackTipReveal = (eventId) => push('tip_reveal', eventId);

/** Followed a ticket link out. The closest thing to a conversion this app has. */
export const trackTicketClick = (eventId) => push('ticket_click', eventId);

/** Followed the event's own website. */
export const trackWebsiteClick = (eventId) => push('website_click', eventId);

/** Opened directions. */
export const trackMapClick = (eventId) => push('map_click', eventId);

// --- site-wide -------------------------------------------------------------------

/** A share link was created. Intent to share. */
export const trackShareCreate = () => push('share_create');

/** Someone opened a shared link. This is reach, as opposed to intent. */
export const trackShareOpen = () => push('share_open');

/** Ran out of cards. High numbers mean the catalog is too thin for the filters in use. */
export const trackStackExhausted = () => push('stack_exhausted');

/** One per page load, as the denominator for everything above. */
export const trackSessionStart = () => push('session_start');

// Exported for tests; not part of the normal surface.
export const __flush = flush;
