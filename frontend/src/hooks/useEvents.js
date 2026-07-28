import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchEvents } from '../api';

// Matches the server's hard ceiling; asking for more is a 422.
const PAGE_SIZE = 20;

const EMPTY = {
  status: 'loading',
  items: [],
  total: 0,
  hasMore: false,
  sampleData: false,
  error: null,
};

/** Loads a filtered page of events and appends further pages on demand. */
export default function useEvents(filters) {
  const [state, setState] = useState(EMPTY);
  const [reloadNonce, setReloadNonce] = useState(0);

  // Filters are a fresh object on every render, so compare by value not identity.
  const filterKey = JSON.stringify(filters);
  const loadingMoreRef = useRef(false);
  const itemsRef = useRef([]);

  useEffect(() => {
    itemsRef.current = state.items;
  }, [state.items]);

  useEffect(() => {
    const controller = new AbortController();
    setState((current) => ({ ...current, status: 'loading', error: null }));

    fetchEvents({ ...filters, limit: PAGE_SIZE, offset: 0, signal: controller.signal })
      .then((data) =>
        setState({
          status: 'ready',
          items: data.items,
          total: data.total,
          hasMore: data.has_more,
          sampleData: data.sample_data,
          error: null,
        }),
      )
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setState((current) => ({ ...current, status: 'error', error: error.message }));
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey, reloadNonce]);

  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current) return;
    loadingMoreRef.current = true;

    try {
      const data = await fetchEvents({
        ...JSON.parse(filterKey),
        limit: PAGE_SIZE,
        offset: itemsRef.current.length,
      });

      setState((current) => {
        // Events can expire between pages, which shifts the offset window. Dedupe so a
        // shifted page can never show the same card twice.
        const known = new Set(current.items.map((item) => item.id));
        return {
          ...current,
          items: [...current.items, ...data.items.filter((item) => !known.has(item.id))],
          total: data.total,
          hasMore: data.has_more,
        };
      });
    } catch {
      // A failed follow-up page leaves everything already loaded intact.
    } finally {
      loadingMoreRef.current = false;
    }
  }, [filterKey]);

  const reload = useCallback(() => setReloadNonce((nonce) => nonce + 1), []);

  return { ...state, loadMore, reload };
}
