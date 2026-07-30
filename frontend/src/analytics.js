// Plausible custom events, mapped to the PRD's success metrics.
//
// Three of the four metrics — swipe sessions, events saved per session, share links
// created — are interactions, not pageviews, so none of them exist without this file.
//
// Two rules:
//
// 1. **Analytics must never break the app.** Every call is wrapped: a blocked script, an
//    ad blocker, or a Plausible outage has to be a silent no-op, not a crash mid-swipe.
// 2. **Nothing identifying is ever sent.** Props carry categories and counts only — no
//    event ids, no share tokens, no venue-level user history. The app's privacy stance is
//    the reason Plausible was chosen over a cookie-based tool, and passing a share token
//    here would quietly undo that.

const enabled = () => typeof window !== 'undefined' && typeof window.plausible === 'function';

function track(name, props) {
  if (!enabled()) return;
  try {
    // Plausible only accepts scalar props, so everything is coerced to a string.
    const payload = props
      ? Object.fromEntries(Object.entries(props).map(([key, value]) => [key, String(value)]))
      : undefined;
    window.plausible(name, payload ? { props: payload } : undefined);
  } catch {
    // Deliberately swallowed — see rule 1.
  }
}

/**
 * A swipe decision, however it was made. Total volume answers "is anyone using it";
 * the save/skip split answers whether the catalog is any good.
 *
 * `method` distinguishes a real gesture from the on-screen buttons or arrow keys, which
 * tells you whether people are actually swiping or just clicking — worth knowing for a
 * product whose whole premise is the gesture.
 */
export const trackSwipe = ({ direction, method }) => track('Swipe', { direction, method });

/**
 * Every save, from wherever it happened. Deliberately overlaps with a right-hand Swipe:
 * `Swipe` measures engagement volume, `Save` measures the saves metric, and keeping them
 * separate means neither has to be derived from the other in the dashboard.
 */
export const trackSave = ({ source, vibe }) => track('Save', { source, vibe });

/** A share link was created — the PRD's organic-spread metric. */
export const trackShareCreated = ({ count, truncated }) =>
  track('Share Created', { count, truncated });

/**
 * Someone opened a shared link. This is the actual spread signal: links created only
 * measures intent, this measures reach.
 */
export const trackSharedListOpened = ({ count }) => track('Shared List Opened', { count });

/** Card expanded. Depth of interest beyond the swipe. */
export const trackDetailOpened = ({ vibe, source }) => track('Detail Opened', { vibe, source });

/** Insider tip revealed — tells you whether the curation is worth the effort. */
export const trackTipRevealed = ({ vibe }) => track('Tip Revealed', { vibe });

/** Ran out of cards. High numbers mean the catalog is too thin for the filters in use. */
export const trackStackExhausted = ({ reason }) => track('Stack Exhausted', { reason });

/** Filters changed. Shows which vibes and price bands people actually reach for. */
export const trackFilterChanged = ({ date, vibes, prices, alcoholFree }) =>
  track('Filter Changed', { date, vibes, prices, alcoholFree });

/** A ticket link was followed out. The closest thing to a conversion this app has. */
export const trackTicketClicked = ({ vibe }) => track('Ticket Clicked', { vibe });
