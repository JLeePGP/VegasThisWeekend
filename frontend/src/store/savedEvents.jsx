// Saved events live in localStorage and nowhere else. No account, no server-side
// identity — the list belongs to the device.
//
// Dismissals used to live here too. They only existed to keep a swiped-away card out of
// the deck; a list has nothing to remove an event from, and an event you scrolled past
// is not a decision worth remembering. The `vtw.dismissed.v1` key is deliberately not
// cleaned up — it expires on its own, and reaching into storage a visitor's browser
// still holds to delete something is worse than leaving a few bytes behind.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const SAVED_KEY = 'vtw.saved.v1';

const SavedEventsContext = createContext(null);

function readJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    // Corrupt payload or storage blocked (Safari private browsing). Start clean.
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Best-effort: a full or blocked store must not break the app.
  }
}

/** Guards against hand-edited or half-written localStorage payloads. */
const looksLikeEvent = (value) =>
  value && typeof value === 'object' && typeof value.id === 'string' && typeof value.name === 'string';

const byStartTime = (a, b) => new Date(a.start_at) - new Date(b.start_at);

export function SavedEventsProvider({ children }) {
  const [saved, setSaved] = useState(() => readJson(SAVED_KEY, []).filter(looksLikeEvent));

  useEffect(() => writeJson(SAVED_KEY, saved), [saved]);

  const save = useCallback((event) => {
    if (!looksLikeEvent(event)) return;
    setSaved((current) =>
      // Re-saving is a no-op rather than a duplicate.
      current.some((item) => item.id === event.id)
        ? current
        : [...current, { ...event, savedAt: Date.now() }],
    );
  }, []);

  const remove = useCallback((id) => {
    setSaved((current) => current.filter((item) => item.id !== id));
  }, []);

  /**
   * Save if it isn't saved, remove it if it is. Returns whether it is saved *now*, which
   * is what lets the caller count a genuine save and stay silent on an undo.
   *
   * The list mutation goes through a functional update so it is always correct against
   * the newest state, while the returned answer is read from the rendered `saved` — the
   * heart the visitor is actually looking at. React does not promise to run an updater
   * before this function returns, so a value set inside one could not be trusted here.
   */
  const toggleSave = useCallback(
    (event) => {
      if (!looksLikeEvent(event)) return false;
      const wasSaved = saved.some((item) => item.id === event.id);

      setSaved((current) => {
        const exists = current.some((item) => item.id === event.id);
        return exists
          ? current.filter((item) => item.id !== event.id)
          : [...current, { ...event, savedAt: Date.now() }];
      });

      return !wasSaved;
    },
    [saved],
  );

  const clearSaved = useCallback(() => setSaved([]), []);

  const value = useMemo(() => {
    const savedIds = new Set(saved.map((item) => item.id));
    return {
      // Chronological, because a saved list is really a plan for the weekend.
      saved: [...saved].sort(byStartTime),
      savedIds,
      isSaved: (id) => savedIds.has(id),
      save,
      remove,
      toggleSave,
      clearSaved,
    };
  }, [saved, save, remove, toggleSave, clearSaved]);

  return <SavedEventsContext.Provider value={value}>{children}</SavedEventsContext.Provider>;
}

export function useSavedEvents() {
  const context = useContext(SavedEventsContext);
  if (!context) throw new Error('useSavedEvents must be used inside SavedEventsProvider');
  return context;
}
