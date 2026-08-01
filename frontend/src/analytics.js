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
//      offline device or a 500 is a silent no-op, never an exception mid-interaction.
//   2. Nothing identifying is ever sent. The payload is a list of {metric, event_id}
//      and there is no third field to add one to.

import { recordInteractions } from './api';

// Interactions are batched rather than sent one request per tap. Flushed on whichever
// comes first.
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

/** Saved, from a list row or from the detail view. */
export const trackSave = (eventId) => push('save', eventId);

/** Opened the detail view. Interest past the row.
 *
 *  There is no counterpart for "decided against it" any more. A swipe left was an
 *  explicit no, which is what made a save *rate* meaningful; scrolling past a row is not
 *  a decision, and counting it as one would invent a denominator. See the note in
 *  backend/app/stats.py on why save_rate is now reported only for the swipe-era data
 *  that can honestly support it. */
export const trackDetailOpen = (eventId) => push('detail_open', eventId);

/** Played an event's video. Says whether the mirroring is earning its cost. */
export const trackVideoPlay = (eventId) => push('video_play', eventId);

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

/** Scrolled to the end of the listing with no more pages to load. High numbers mean the
 *  catalog is too thin for the filters in use — the successor to the deck's
 *  `stack_exhausted`, which was 31% of sessions and the reason sourcing, rather than
 *  layout, is the thing to fix next. */
export const trackListEnd = () => push('list_end');

/** Submitted an email address. The signup itself is a row in `subscribers`; this counter
 *  is the site-wide total, so the conversion can be read against sessions without
 *  querying the address table at all. */
export const trackSubscribe = () => push('subscribe');

/** One per page load, as the denominator for everything above. */
export const trackSessionStart = () => push('session_start');

/**
 * True when this page is running as an installed app rather than in a browser tab.
 *
 * Two checks because the platforms disagree. `display-mode` is the standard and is what
 * Android reports; `navigator.standalone` is Safari's own flag and is what iOS home
 * screen apps have had for years. Either one being true is enough.
 */
export function isStandalone() {
  try {
    return (
      window.matchMedia?.('(display-mode: standalone)').matches === true ||
      window.navigator.standalone === true
    );
  } catch {
    return false;
  }
}

/**
 * A session opened from the home screen.
 *
 * Deliberately counted per session rather than per install. Safari fires no install
 * event of any kind — an iPhone user adding this to their home screen is invisible — so
 * an install counter would be Android-only and would read as "nobody installs" for an
 * audience that is mostly iPhone.
 *
 * Read against `session_start` it answers the question the install was for: do people
 * who install come back, and does saving survive for them. An install nobody opens is
 * worth nothing, and this counts the opening.
 */
export const trackStandaloneSession = () => push('standalone_session');

/** Chromium's `appinstalled`. Android and desktop Chrome only — see above. */
export const trackAppInstalled = () => push('app_installed');

// Exported for tests; not part of the normal surface.
export const __flush = flush;
