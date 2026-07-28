// Saved and dismissed events live in localStorage and nowhere else. No account, no
// server-side identity — the list belongs to the device.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const SAVED_KEY = 'vtw.saved.v1';
const DISMISSED_KEY = 'vtw.dismissed.v1';

// Dismissals fade out, otherwise the stack would eventually be empty forever with no way
// back other than clearing site data.
const DISMISSAL_TTL_MS = 14 * 86_400_000;

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

function prunedDismissals(raw) {
  if (!raw || typeof raw !== 'object') return {};
  const cutoff = Date.now() - DISMISSAL_TTL_MS;
  return Object.fromEntries(
    Object.entries(raw).filter(([, at]) => typeof at === 'number' && at > cutoff),
  );
}

const byStartTime = (a, b) => new Date(a.start_at) - new Date(b.start_at);

export function SavedEventsProvider({ children }) {
  const [saved, setSaved] = useState(() => readJson(SAVED_KEY, []).filter(looksLikeEvent));
  const [dismissed, setDismissed] = useState(() => prunedDismissals(readJson(DISMISSED_KEY, {})));

  useEffect(() => writeJson(SAVED_KEY, saved), [saved]);
  useEffect(() => writeJson(DISMISSED_KEY, dismissed), [dismissed]);

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

  const dismiss = useCallback((id) => {
    setDismissed((current) => ({ ...current, [id]: Date.now() }));
  }, []);

  const resetDismissed = useCallback(() => setDismissed({}), []);

  const clearSaved = useCallback(() => setSaved([]), []);

  const value = useMemo(() => {
    const savedIds = new Set(saved.map((item) => item.id));
    return {
      // Chronological, because a saved list is really a plan for the weekend.
      saved: [...saved].sort(byStartTime),
      savedIds,
      dismissedIds: new Set(Object.keys(dismissed)),
      dismissedCount: Object.keys(dismissed).length,
      isSaved: (id) => savedIds.has(id),
      save,
      remove,
      dismiss,
      resetDismissed,
      clearSaved,
    };
  }, [saved, dismissed, save, remove, dismiss, resetDismissed, clearSaved]);

  return <SavedEventsContext.Provider value={value}>{children}</SavedEventsContext.Provider>;
}

export function useSavedEvents() {
  const context = useContext(SavedEventsContext);
  if (!context) throw new Error('useSavedEvents must be used inside SavedEventsProvider');
  return context;
}
