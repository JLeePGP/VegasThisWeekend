// All network access goes through here. No secrets ever reach the client, so every
// external call is proxied by the FastAPI backend rather than made from the browser.

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { body, signal, method = 'GET' } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      signal,
      // A Content-Type header on a GET would force a CORS preflight for nothing.
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause;
    throw new ApiError("Can't reach the server. Check your connection.", 0);
  }

  if (!response.ok) {
    throw new ApiError(await errorMessageFor(response), response.status);
  }
  return response.json();
}

async function errorMessageFor(response) {
  if (response.status === 429) return 'Slow down a moment, then try again.';
  if (response.status === 404) return 'Not found.';
  try {
    const payload = await response.json();
    if (typeof payload?.detail === 'string') return payload.detail;
  } catch {
    // Non-JSON error body; fall through to the generic message.
  }
  return 'Something went wrong. Try again.';
}

export function fetchEvents({
  date,
  vibes = [],
  prices = [],
  alcoholFree = false,
  limit = 20,
  offset = 0,
  signal,
} = {}) {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  for (const vibe of vibes) params.append('vibe', vibe);
  for (const price of prices) params.append('price', price);
  // Only sent when on. The server defaults it to false, and an explicit
  // alcohol_free=false in every URL would make the cache key noisier for nothing.
  if (alcoholFree) params.set('alcohol_free', 'true');
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return request(`/events?${params}`, { signal });
}

export const fetchEvent = (id, { signal } = {}) => request(`/events/${id}`, { signal });

export const createShareList = (eventIds) =>
  request('/share', { method: 'POST', body: { event_ids: eventIds } });

export const fetchShareList = (token, { signal } = {}) => request(`/share/${token}`, { signal });

/**
 * Fire-and-forget interaction counts.
 *
 * Does not go through `request`: this must never surface an error into the app, and it
 * needs `keepalive` so a flush triggered by the page going away still completes.
 */
export function recordInteractions(items) {
  if (!items?.length) return;
  try {
    fetch(`${API_BASE}/interactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Blocked by an extension, offline, or the keepalive quota is exhausted. Counting
    // is not worth an exception in the middle of a swipe.
  }
}
