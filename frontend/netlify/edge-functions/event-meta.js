// Per-event share previews.
//
// The app is client-rendered, so every /e/<id> URL served the same static <head>: one
// generic title, the site's own card image, and an og:url pointing at the homepage. A
// friend pasting a specific event into a group chat got a preview that named neither the
// event nor the night it was on — and pasted links are this project's growth loop, not
// decoration. The tags exist in index.html; they were simply the same on every page.
//
// This rewrites them at the edge. Netlify runs it before the SPA fallback, so
// `context.next()` returns the built index.html and we substitute into it. The bundle,
// the router and every browser behaviour are untouched: only the markup a scraper reads
// before any JavaScript runs is different.
//
// It never blocks the page. A slow API, a 404, a malformed id or a shape we did not
// expect all return the original HTML — a generic preview is a much smaller problem than
// an event page that will not load.

const API_BASE = Netlify.env.get("API_BASE_URL") ?? "https://api.vegasthisweekend.com";
const SITE = "https://vegasthisweekend.com";

// Ids are 32 hex characters. Checking here means a junk URL costs nothing rather than an
// API round trip on every crawl of every mistyped link.
const ID_PATTERN = /^[0-9a-f]{32}$/;

// Past this, serve the generic preview rather than keep a visitor waiting. Scrapers give
// up quickly too, so a slow answer is worth no more than no answer.
const API_TIMEOUT_MS = 1500;

const escapeAttribute = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

/**
 * Replace a meta tag by the attribute that identifies it.
 *
 * Matched with a regex rather than exact strings because index.html writes some of these
 * across several lines for readability and Vite preserves that. `[^>]` already matches
 * newlines, so one pattern handles both shapes; keying on the identifying attribute
 * rather than the whole tag means reformatting index.html cannot silently stop this
 * working.
 */
function replaceMeta(html, attribute, key, content) {
  const pattern = new RegExp(`<meta[^>]*${attribute}="${key}"[^>]*>`, "i");
  if (!pattern.test(html)) return html;
  return html.replace(
    pattern,
    `<meta ${attribute}="${key}" content="${escapeAttribute(content)}" />`,
  );
}

function removeMeta(html, attribute, key) {
  return html.replace(new RegExp(`\\s*<meta[^>]*${attribute}="${key}"[^>]*>`, "i"), "");
}

const VEGAS = "America/Los_Angeles";

/** "Sat, Aug 1 · 9:00 PM" — the detail people decide on, in Vegas time like the app. */
function whenLabel(startAt) {
  const start = new Date(startAt);
  if (Number.isNaN(start.getTime())) return "";
  const day = start.toLocaleDateString("en-US", {
    timeZone: VEGAS,
    weekday: "short",
    month: "short",
    day: "numeric",
  });
  const time = start.toLocaleTimeString("en-US", {
    timeZone: VEGAS,
    hour: "numeric",
    minute: "2-digit",
  });
  return `${day} · ${time}`;
}

/** One line a person can act on, kept under the ~200 characters previews show. */
function describe(event) {
  const when = whenLabel(event.start_at);
  const where = [event.venue, event.neighborhood].filter(Boolean).join(", ");
  const lead = [when, where].filter(Boolean).join(" · ");
  const detail = (event.hook || event.description || "").trim();

  const full = detail ? `${lead}. ${detail}` : lead;
  return full.length > 200 ? `${full.slice(0, 197).trimEnd()}…` : full;
}

export default async (request, context) => {
  const response = await context.next();

  // Only the HTML shell is rewritten. An asset that happens to sit under this path, or
  // an error page, is passed through untouched.
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("text/html")) return response;

  const id = new URL(request.url).pathname.split("/")[2] ?? "";
  if (!ID_PATTERN.test(id)) return response;

  let event;
  try {
    const apiResponse = await fetch(`${API_BASE}/events/${id}`, {
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
      headers: { accept: "application/json" },
    });
    if (!apiResponse.ok) return response;
    event = await apiResponse.json();
  } catch {
    // Timeout, DNS, a 500, malformed JSON. The generic preview is the fallback and the
    // page itself still works — the app fetches the event again on the client.
    return response;
  }

  if (!event?.name) return response;

  const title = `${event.name} — Vegas This Weekend`;
  const description = describe(event);
  const url = `${SITE}/e/${id}`;

  let html = await response.text();

  html = html.replace(/<title>[^<]*<\/title>/i, `<title>${escapeAttribute(title)}</title>`);
  html = html.replace(
    /<link[^>]*rel="canonical"[^>]*>/i,
    `<link rel="canonical" href="${url}" />`,
  );

  html = replaceMeta(html, "name", "description", description);
  html = replaceMeta(html, "property", "og:title", title);
  html = replaceMeta(html, "property", "og:description", description);
  html = replaceMeta(html, "property", "og:url", url);
  html = replaceMeta(html, "name", "twitter:title", title);
  html = replaceMeta(html, "name", "twitter:description", description);

  // The event's own image when it has one. Events without artwork keep the site card,
  // which is a designed 1200x630 — better than nothing at all, and its declared
  // dimensions stay true.
  if (event.image_url) {
    html = replaceMeta(html, "property", "og:image", event.image_url);
    html = replaceMeta(html, "name", "twitter:image", event.image_url);
    html = replaceMeta(html, "property", "og:image:alt", event.name);
    // Dropped rather than guessed. Event artwork is whatever the venue published —
    // usually portrait — and declaring 1200x630 over it is a statement that is simply
    // false, which some scrapers use to crop.
    html = removeMeta(html, "property", "og:image:width");
    html = removeMeta(html, "property", "og:image:height");
    html = removeMeta(html, "property", "og:image:type");
  }

  const headers = new Headers(response.headers);
  // Recomputed: the substituted markup is a different length, and a stale
  // content-length truncates the page.
  headers.delete("content-length");

  return new Response(html, {
    status: response.status,
    headers,
  });
};

export const config = { path: "/e/*" };
