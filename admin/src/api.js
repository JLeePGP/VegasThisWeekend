// All admin network calls. The token lives in localStorage rather than a file so it
// never ends up committed, and is sent as a bearer header on every request.

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');
const TOKEN_KEY = 'vtw.admin.token';

export const getStats = (days = 30) => request(`/admin/stats?days=${days}`);

export const submitExtractions = (urls) =>
  request('/admin/extractions', { method: 'POST', body: { urls } });

export const listExtractions = ({ refresh = true } = {}) =>
  request(`/admin/extractions?refresh=${refresh}`);

export const discardExtraction = (id) =>
  request(`/admin/extractions/${id}/discard`, { method: 'POST' });

/** Links an approved draft to the event it produced. Best-effort: the event is already
 *  saved by this point, so a failure here must not look like the save failed. */
export const markExtractionApproved = (id, eventId) =>
  request(`/admin/extractions/${id}/mark-approved?event_id=${eventId}`, { method: 'POST' });

export const readToken = () => {
  try {
    return window.localStorage.getItem(TOKEN_KEY) ?? '';
  } catch {
    return '';
  }
};

export const writeToken = (token) => {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage blocked; the token simply won't survive a reload.
  }
};

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    // Carries the duplicate collisions on a 409.
    this.payload = payload;
  }
}

async function request(path, { method = 'GET', body } = {}) {
  const token = readToken();
  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(`Can't reach the API at ${API_BASE || 'the configured origin'}.`, 0);
  }

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // Some errors have no JSON body.
  }

  if (!response.ok) {
    throw new ApiError(messageFor(response.status, payload), response.status, payload);
  }
  return payload;
}

function messageFor(status, payload) {
  if (status === 401) return 'That admin token was rejected.';
  if (status === 503) return 'The API has no ADMIN_TOKEN configured, so admin routes are off.';
  if (status === 429) return 'Rate limited — wait a moment and retry.';

  const detail = payload?.detail;
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors arrive as a list of {loc, msg}.
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${(item.loc ?? []).slice(1).join('.') || 'request'}: ${item.msg}`)
      .join('; ');
  }
  return `Request failed (${status}).`;
}

export const getStatus = () => request('/admin/status');

export const extract = ({ url, text }) =>
  request('/admin/extract', { method: 'POST', body: url ? { url } : { text } });

export const listEvents = ({ q = '', includeInactive = true } = {}) => {
  const params = new URLSearchParams({ include_inactive: String(includeInactive), limit: '200' });
  if (q.trim()) params.set('q', q.trim());
  return request(`/admin/events?${params}`);
};

export const createEvent = (payload, { force = false } = {}) =>
  request(`/admin/events${force ? '?force=true' : ''}`, { method: 'POST', body: payload });

export const updateEvent = (id, payload) =>
  request(`/admin/events/${id}`, { method: 'PUT', body: payload });

export const deactivateEvent = (id) =>
  request(`/admin/events/${id}/deactivate`, { method: 'POST' });

export const listTips = () => request('/admin/tips');
export const createTip = (payload) => request('/admin/tips', { method: 'POST', body: payload });
export const updateTip = (id, payload) =>
  request(`/admin/tips/${id}`, { method: 'PUT', body: payload });
export const deleteTip = (id) => request(`/admin/tips/${id}`, { method: 'DELETE' });

export { API_BASE };
