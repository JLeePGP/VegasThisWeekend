# Backlog

Working list. Add items freely — we work through this next session.

Grouped by who can do it and what it unblocks, rather than by size. Anything marked
**John** needs a dashboard or an account I have no access to.

---

## 1. Finish the launch

These are the only things between the current state and a site that is safe to promote.

| # | Item | Owner | Notes |
|---|---|---|---|
| 1.1 | **Netlify TLS certificate for `vegasthisweekend.com` + `www`** | waiting | DNS is correct and the domain is attached — Netlify is still serving its `*.netlify.app` wildcard, which is what makes browsers say "not secure". Nothing to fix. If still failing, **Domain management → HTTPS → Verify DNS configuration**, then **Provision certificate**. |
| 1.2 | **Enable Force HTTPS** | John | Only becomes available once 1.1 completes. Until then `http://vegasthisweekend.com` serves insecurely with no redirect. |
| 1.3 | **Point `VITE_API_BASE_URL` at `https://api.vegasthisweekend.com`** | John | Netlify → Environment variables → **edit** the existing one (don't delete/recreate), then **trigger a deploy**. It is compiled in at build time, so editing alone does nothing. The deployed bundle still calls the `railway.app` hostname. |
| 1.4 | **Register the nine Plausible goals** | John | Swipe · Save · Share Created · Shared List Opened · Detail Opened · Tip Revealed · Stack Exhausted · Filter Changed · Ticket Clicked. Events are firing already, but Plausible shows nothing until each is added as a *custom event* goal — so it looks broken until this is done. |
| 1.5 | **Verify Plausible is actually recording** | — | `data-domain` is `vegasthisweekend.com` while the site was being served from `netlify.app`. Worth confirming events land once the real domain is live, rather than assuming. |
| 1.6 | **Drop `railway.app` from the CSP `connect-src`** | me | Only after 1.3 is confirmed. Both origins are allowed right now purely to avoid a broken window during the cutover; a stale allowed origin is harmless but misleading. |

---

## 2. Do not skip: operational risk

| # | Item | Owner | Why it matters |
|---|---|---|---|
| 2.1 | **Database backups on Railway** | John | Events are hand-entered. Ten so far, more coming. If that Postgres instance is lost that work is gone, and some Railway tiers have no automated backups. Worth settling **before** entering another forty. |
| 2.2 | **Decide the canonical hostname** | John | Apex or `www`. Netlify redirects one to the other. Affects what share links look like in a text message — apex is shorter and reads better. |
| 2.3 | **Add Sunday events** | John | "This Weekend" spans Fri–Sun and Sunday is currently empty, so the default view thins out as the weekend progresses. |

---

## 3. Launch-readiness gaps found in the 29 Jul audit

| # | Item | Notes |
|---|---|---|
| 3.1 | **`og:image` for share previews** | The highest-value item here. Growth depends on people pasting links into group chats, and those previews currently render as a blank grey box. Card design is done and committed at `frontend/tools/og-image/` — **it has not been rendered to PNG or wired into `index.html` yet**. Run `node render-og.mjs` from that directory, then add `og:image`, `og:url`, `twitter:card` meta tags. |
| 3.2 | **React error boundary** | Any component that throws currently unmounts the tree and leaves a white screen with no explanation and no way back. Should become "something went wrong, reload". |
| 3.3 | **`robots.txt`** | Absent entirely; crawlers get no guidance. |
| 3.4 | **Web app manifest** | Would make a mobile-first app installable to the home screen. Cheap, and closer to the "native app" v2 goal than a rewrite. |

---

## 4. Product

Full modelling reasoning for 4.1 and 4.2 is in the README under *Design note: the Sober
and Fitness filters*.

| # | Item | Notes |
|---|---|---|
| 4.1 | **Sober filter** | **Not a vibe** — it cuts across categories. A sober rave is `nightlife` AND alcohol-free; adding `SOBER` to the vibe enum would make a sober club night impossible to express. Needs `Event.alcohol_free` (the first real migration after the baseline), its own query param, and a toggle that composes with the vibe chips. Extraction must only set it on an explicit signal — "no alcohol mentioned" is not evidence, and guessing optimistically sends someone in recovery to a bar. |
| 4.2 | **Fitness vibe** | This one *is* a vibe, and fills a real hole (an indoor class fits none of the current nine). Needs an enum value, both `constants.js` files, and a `--vibe-fitness-*` colour pair. No migration — `Event.vibe` is a plain string column. |
| 4.3 | **SEO / crawlability** | Strategic, not a bug. The PRD's premise is displacing *"Googling things to do in Vegas this weekend"*, but the app is one client-rendered URL with one generic title and no per-event pages — there is nothing for Google to index. Real fix is per-event routes with server-rendered metadata, which is a v2-sized conversation. |
| 4.4 | **Eventbrite API** | Config placeholder only; never wired up. |

---

## 5. Known technical debt

| # | Item | Notes |
|---|---|---|
| 5.1 | **Cloudflare R2 unconfigured** | Image mirroring is built and tested but inert. Until then real events keep their external image URLs, which break when a venue redesigns — the exact problem R2 was chosen to solve. |
| 5.2 | **`img-src https:` in the CSP** | Relaxed so external event images load at all while 5.1 is outstanding. Trade-off: third-party image hosts see visitors' IPs, which sits awkwardly with the app's otherwise no-third-parties stance. Tightenable to one domain once R2 is live; nothing breaks visually, since failed images fall back to a generated poster. |
| 5.3 | **Editing a series** | A residency expands to one row per night, so changing it means editing each night. Fine at 26 occurrences, not at a hundred. |
| 5.4 | **Offset pagination** | Can skip or repeat an item if an event expires mid-scroll. The client dedupes by id, so the worst visible symptom is a slightly short page. |
| 5.5 | **In-process rate limiting** | Limits are per-instance. Fine at one instance; a second needs shared storage. |
| 5.6 | **Extraction `effort` untuned** | Sits at the default `high`. `medium` would likely cut thinking tokens with no quality loss on a task this well specified — worth measuring rather than guessing. |
| 5.7 | **JS-rendered pages defeat URL extraction** | Confirmed against vegas.com: the fetch returns meta tags and a tag-manager reference, no event data. Instagram and TikTok are login-walled and unreachable by any server-side fetch. The paste-text box is the answer for both, and it works — but it is the workflow for a real slice of sources, not an edge case. |

---

## 6. John's additions

<!-- Add anything here. -->
