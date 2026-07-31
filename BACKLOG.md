# Backlog

Consolidated 30 Jul 2026 — John's feedback merged with the 29 Jul audit.

---

## Session close — 30 Jul 2026

Session ended here. John moves to **adding events and finding users**; the build work
pauses.

### Links

| What | Where |
|---|---|
| Site | https://vegasthisweekend.com |
| API | https://api.vegasthisweekend.com |
| Admin panel | `cd admin && npm run dev` → http://127.0.0.1:5174 — local only, never deployed |
| Repo | https://github.com/JLeePGP/VegasThisWeekend |
| Behaviour analytics | Admin panel → **Stats** tab |
| Traffic analytics | Cloudflare → `vegasthisweekend.com` → Analytics & Logs → Traffic |
| Extraction spend | https://console.anthropic.com → Usage |
| API health | Railway → the API service → Metrics |

Full detail on all four analytics surfaces is in the README.

### State at close

- 293 tests passing; frontend and admin bundles both build
- Working tree clean, everything pushed through `e929761`
- 10 real events in production, no sample data
- `ANTHROPIC_API_KEY` set on Railway — extraction and the bulk queue are **live**, on
  `claude-sonnet-5`
- Audited: the key cannot reach an HTTP response. API errors are re-raised carrying the
  status code only, never the SDK's exception text

### What is built but not yet switched on

All of it is dashboard work, all of it in [OPERATIONS.md](OPERATIONS.md) with the check
that proves each one worked — most fail silently, which is the whole reason those checks
are written down.

1. **R2 credentials** — media mirroring is inert without them, so cards still load from
   venue CDNs, which see every visitor who opens them
2. **Cloudflare cache rule** — the API sends the caching headers already; Cloudflare
   ignores them until the rule exists (`cf-cache-status` currently reads `DYNAMIC`)
3. **Web Analytics toggle** — confirmed not currently injecting, but confirm the toggle
4. **Proxy shared secret** — two-stage; stage 1 rejects nothing and is safe to deploy first
5. **Backups** — turn on scheduled snapshots, run `scripts/verify_backup.py`, and restore
   one by hand at least once

### Two things to watch once real users arrive

- **`stack_exhausted`** in the Stats tab. It means people ran out of cards for the filters
  they picked — the earliest and clearest signal that the catalog is too thin.
- **`share_open` vs `share_create`.** Created is intent; opened is actual reach. If the gap
  is wide, links are being made and not travelling.

### Suggested first move next session

Expose the deployed commit SHA on `/health`. Railway already provides it in the
environment, and it turns "is my change actually live?" into a single curl — this session
needed a contrived probe to answer that question without writing to production.

## ✅ Shipped 30 Jul 2026

| # | Item | Commit |
|---|---|---|
| C1 | Dropped the stale `railway.app` origin from the CSP | `7fc44b3` |
| C2 | React error boundary — no more white-screen on a render error | `7fc44b3` |
| C3 | OG image rendered and wired up; shared links preview properly | `7fc44b3` |
| A1 | Full-screen card, chrome floating over the media | `db17b8b` |
| A1a | Video playback — the field existed, the player never did | `db17b8b` |
| A1b | Richer generated posters (bands + ghost word) | `db17b8b` |
| A1c | Swipe labels moved to the stack, much louder | `db17b8b` |
| A1d | Per-event Tickets / Website links, each hidden when absent | `db17b8b` |
| A2 | Share panel: the URL, copy state, expiry, snapshot semantics | `a902ca5` |
| A3 | Preview button — opens exactly what the recipient sees | `a902ca5` |
| — | CSP: `media-src`, Plausible shim hash, Cloudflare beacon | `2fdf23a` |
| 4.1 | **Sober filter** — `alcohol_free` column + its own switch, ANDs with categories | `d7ed64e` |
| 4.2 | **Fitness** category | `d7ed64e` |
| B1 | **Street address** + free Google Maps deep link (no API key) | `d7ed64e` |
| B2 | **Multiple categories per event** — `primary vibe` + additive tag rows | `d7ed64e` |
| — | `source_url` exposed publicly — the Website link had been dead | `d7ed64e` |
| B3 | **First-party analytics** — counters, admin dashboard, Plausible retired | `bfb1ade` |
| B4 | **Bulk URL extraction** — paste a list, server-side queue, review each | `1e56386` |
| B4a | Separate link fields on extract (they already existed as columns) | `d7ed64e` |
| C10 | Extraction `effort` measured — see the note in `extraction.py` | `5b83047` |
| C5 | **Rate limiting keyed on the real visitor**, not the proxy | `c40f2ff` |

### Privacy & scale pass — 30 Jul 2026

Built against one requirement: the experience should be the same for one visitor or a
hundred thousand, and no visitor should be identifiable to us or to anyone else.

| Item | What changed | Why it mattered |
|---|---|---|
| Edge caching | `/events` and `/events/{id}` send `s-maxage=60, stale-while-revalidate=120`; nothing else does | Without it, a thousand concurrent visitors is a thousand identical Postgres queries |
| Query reduction | Sample-data COUNT and the tip table are cached in-process for 30s, invalidated on every admin write | Four DB round trips per listing became two |
| Batched counters | Interaction upserts go in as at most two multi-row statements | Twenty swipes across ten events was twenty INSERTs; it's now two, at any batch size |
| Cloudflare beacon | Removed from the CSP entirely — `script-src` is now bare `'self'` | Edge-injected, so it never appeared in the repo. Third-party script on every page, telling us what our own counters already do |
| R2 for video | Mirroring generalised from images to video, own size cap and timeout | Every off-origin URL hands that host the visitor's IP and referring page. Mirroring means the browser talks to our bucket and nobody else |
| Proxy hardening | Shared secret from a Cloudflare Transform Rule; unverified requests get keyed on their socket peer, and can be refused outright | `CF-Connecting-IP` was forgeable via the raw Railway hostname — enough to exhaust *another* visitor's rate limit |
| Backup verification | `backend/scripts/verify_backup.py` — dump, restore to scratch, compare row counts, drop | An untested backup is a guess, and there are hand-entered events in production now |

**All of it needs dashboard work to take effect** — R2 credentials, the cache rule, the
Transform Rule, the analytics toggle, the backup schedule. Every step, and the check that
proves each one actually worked, is in [OPERATIONS.md](OPERATIONS.md).

**C5 was a live bug, now confirmed rather than suspected.** The deployed API reported its
socket peer as `100.64.0.2` — RFC 6598 shared space, Railway's internal proxy — so every
visitor on earth shared one bucket and the 100/min public limits were 100/min *in total*.
Asked the API directly via a new admin diagnostics endpoint instead of reasoning about it.

The same measurement killed the obvious alternative: `X-Forwarded-For`'s first entry was
`104.23.203.139`, a **Cloudflare edge address**, not the visitor. Keying on that would
have traded one shared bucket for one bucket per Cloudflare PoP and looked like it worked.

**Extraction cost, finally measured rather than estimated.** Prompt caching on the
continuation loop took the worst observed run from **$0.48 to $0.17** and collapsed the
spread from 3.4× to 1.5× — the problem was never a high average, it was the same page
costing wildly different amounts because a `pause_turn` resend carried the whole fetched
page again at full price. Median is now **$0.12/URL**: ~$27/month sync at 50 events a
week, **~$13.50 batched**.

Three hypotheses were wrong before that one was right — a content cap (hurt accuracy on
the start time), `effort` (run-to-run noise swamped it), and `max_uses=1` (worse on both
cost *and* accuracy). All three are recorded in `extraction.py` with their numbers, so
the next attempt starts from data. Total measurement spend: about $2.23.

**Migration `b2c7d41ae903` applied to production 30 Jul**, all 10 events intact.
Deliberately additive — nothing dropped, renamed or rewritten — so it was safe to run
without confirmed backups, and reversible. `neighborhood` is untouched and stays until
real addresses are populated and checked; dropping it is a separate later step.

**Deployed and verified live on 30 Jul**, including a video actually playing on
`vegasthisweekend.com` (readyState 4, 480×854, playhead advancing).

Three things only appeared once a browser was pointed at the deployed site — none of
them reproduce in dev, where Netlify's `_headers` is not applied:

- **`media-src` was missing, so every event video was blocked in production.** With no
  `media-src` the browser falls back to `default-src 'self'` and silently refuses
  off-origin media, so the player rendered perfectly and played nothing. The two live
  CloudFront videos were blocked from the moment the feature shipped.
- **The Plausible queue shim had been blocked all along** — the violation hash matched
  its exact bytes. Custom events fired before Plausible's deferred script loaded were
  being dropped, which would read as flaky analytics rather than a policy problem.
- **Cloudflare Web Analytics was enabled and blocked.** Its beacon is injected at the
  edge, so it appears in no file in this repo — grepping the source would never find it.

Two bugs found by testing rather than by eye, both fixed:

- **The share button stuck on "Creating link…".** `handleShare` awaited
  `navigator.share`, so the button stayed busy for as long as the native sheet was
  open — or forever if it never settled. The link already exists by that point, so the
  busy state now clears before the hand-off.
- **The swipe labels' real problem wasn't size.** They lived inside the card, so they
  travelled with it and slid off the edge of the screen at exactly the moment you
  needed to read them. Moving them to the stack fixed what making them bigger could not.

Still to do from this group: nothing.

---

**Effort key:** **S** = under an hour · **M** = a few hours, may touch the schema · **L** = a full session or more.
**Launch** = should be done before actively promoting the site. Everything else is real work, just not gating.

---

## Recommended order

We'll likely do all of it. This is the sequence that avoids rework, not a ranking of value.

1. **§C1–C3 housekeeping** (~1 hr total) — CSP cleanup, error boundary, OG image. Small, unblocks sharing.
2. **§A1 the card rebuild** — full-screen + video + better default posters + the links row. These are one workstream, not four; doing them separately means building the same component three times.
3. **§B1 address→neighborhood** and **§B2 multi-category** — both are migrations. Batch them into one Alembic revision.
4. **§A4 Sober + Fitness** — depends on B2 landing first (see the note there; it's the one item where the obvious approach is wrong).
5. **§B3 first-party analytics** — replaces Plausible rather than supplementing it, so it also settles the Cloudflare/Plausible question.
6. **§B4 bulk URL extraction** — the biggest single build. Cost math has changed materially; see below.

---

## A. User-facing

| # | Item | Launch | Effort | Notes |
|---|---|:---:|:---:|---|
| **A1** | **Full-screen card (TikTok-style)** | ✅ | **L** | The four items below are one rebuild. Media goes edge-to-edge; header and footer float over it with a scrim. Watch for: iOS `100vh` (use `dvh`), safe-area insets, and the gesture area now sitting under the floating buttons. |
| A1a | └ Video playback | ✅ | **M** | `video_url` already exists in the model, the API, and the admin form — **the frontend just never renders it.** Needs a `<video>` with `muted` + `playsinline` + `loop` + `autoplay` (all four, or iOS refuses), poster fallback, and pause-when-offscreen. ⚠️ Hotlinked video from venues and Instagram usually fails (CORS, hotlink protection, expiring URLs) — this likely forces **C6 (R2)** sooner than planned. |
| A1b | └ Better default posters | ✅ | **M** | Currently a colored panel with a word — fine at card size, weak at full-screen. Options: richer generated art (gradient mesh + big type + vibe glyph + venue), or a small curated set of Vegas stock per vibe. Design call needed. |
| A1c | └ Swipe labels (SAVE / SKIP) | ✅ | **S** | Too faint. Bigger, higher contrast, earlier reveal threshold, slight scale-on-progress. |
| A1d | └ Links row: Tickets vs Website | — | **S** | `ticket_url` **and** `source_url` both already exist. Render each only when present, and label them differently — a free yoga class shouldn't show a Tickets button. Cheap because the schema is already right. |
| **A2** | **Share confirmation** | ✅ | **S** | No feedback that a link was created or copied. Needs a toast plus the URL shown in text so it's verifiable. Note `navigator.share` and clipboard both need HTTPS — now satisfied. |
| **A3** | **Preview what a shared link opens** | — | **S** | Separate from A2: you can't currently check what a recipient sees. A "preview" affordance on the share sheet, or just open it in a new tab. |
| **A4** | **Sober + Fitness filters** | — | **M** | ⚠️ Read the design note in the README before building. **Fitness is a vibe; Sober is not** — and B2 (multi-category) makes it *look* solved without solving it. Details in §Decisions below. |
| **A5** | SEO / crawlability | — | **L** | Strategic. One client-rendered URL, no per-event pages — nothing for Google to index, which sits against the PRD's "displace Googling it" premise. Real fix is per-event routes with server-rendered metadata. v2-sized. |

---

## B. Admin

| # | Item | Launch | Effort | Notes |
|---|---|:---:|:---:|---|
| **B1** | **Address replaces neighborhood** | — | **M** | Agreed — two location fields is one too many. Plan: add `address`, keep `neighborhood` as a *derived* field, and have the AI infer it on save. Free maps deep-link (`https://maps.google.com/?q=<address>`) needs **no** Google API key or billing account — worth avoiding. Needs a migration + backfill for the 10 existing events. |
| **B2** | **Multiple categories per event** | — | **M** | Real constraint: the generated poster colors and the vibe chip both assume exactly one vibe. Recommendation: keep a **`primary_vibe`** (drives color and display) plus a **`tags[]`** array (drives filtering). That gets "yoga networking = fitness + outdoors" without redesigning the visual system. Migration required (`vibe` is currently a plain `String(32)`). |
| **B3** | **Analytics you can actually see** | — | **L** | ⚠️ There's a real tension here, worth reading §Decisions. Short version: Plausible **cannot** tell you which events get saved most, because we deliberately never send event IDs. Getting per-event numbers means first-party aggregate counters in our own database — which is also more private, needs no third-party script, and costs nothing. |
| **B4** | **Bulk URL extraction** | — | **L** | Cost has changed a lot since you passed on this — see §Decisions. Design: paste many URLs → queue → each becomes a *draft* → you approve/edit in a review screen. Never auto-publish. |
| B4a | └ Separate link fields on extract | — | **S** | You asked for main link / ticket link / media link. All three columns already exist (`source_url`, `ticket_url`, `image_url`/`video_url`) — this is prompt + form work, not schema work. |
| **B5** | Editing a recurring series | — | **M** | A residency expands to one row per night, so changing it means editing each night. Fine at 26, painful at 100. |

---

## C. Platform & housekeeping

| # | Item | Launch | Effort | Notes |
|---|---|:---:|:---:|---|
| **C1** | Drop `railway.app` from CSP `connect-src` | ✅ | **S** | Verified the deployed bundle now calls only `api.vegasthisweekend.com`. Stale entry, safe to remove. |
| **C2** | React error boundary | ✅ | **S** | Any render error currently white-screens the whole app with no recovery. |
| **C3** | OG image + meta tags | ✅ | **S** | Card is designed at `frontend/tools/og-image/` but **never rendered to PNG**; `og:image` / `twitter:card` tags absent. Highest-leverage small item — links pasted into group chats currently preview as a grey box, and that's the growth loop. |
| **C4** | Railway Postgres backups | ✅ | **S** | Still unconfirmed. Ten hand-entered events, about to become fifty. |
| **C5** | Rate limiting behind Cloudflare | ✅ | **S** | `limiter.py:13` keys on `get_remote_address` → `request.client.host`, which behind Cloudflare **and** Railway is a proxy IP. If so, all visitors share one 100/min bucket and real users could hit 429s. Fix is `CF-Connecting-IP`. Needs verifying first — and note the raw `railway.app` host is still public, so that header is spoofable by anyone bypassing Cloudflare. |
| **C6** | Cloudflare R2 | — | **M** | Built and tested but inert. Becomes near-mandatory once video lands (A1a) — you can't reliably hotlink venue or Instagram media. Also lets us tighten `img-src` from `https:` to one domain. |
| **C7** | Web app manifest | — | **S** | Makes it installable to the home screen. Closest thing to the v2 "native app" goal without a rewrite. |
| **C8** | `robots.txt` | — | **S** | Cloudflare now serves a managed AI content-signals file, so this is partly handled — but it's Cloudflare's, not ours, and has no sitemap reference. |
| **C9** | CI (GitHub Actions) | — | **S** | 161 tests only run when I run them locally. A broken commit deploys to Railway unnoticed. ~20 lines. |
| **C10** | Tune extraction `effort` | — | **S** | Still at the default `high`. Only matters if B4 goes ahead. |
| **C11** | Offset pagination | — | **S** | Can skip or repeat an item if an event expires mid-scroll. Client dedupes by id, so worst case is a slightly short page. |

---

## Decisions — settled 30 Jul 2026

All three resolved with John. Recorded so they don't get re-opened by accident.

| Decision | Outcome |
|---|---|
| Analytics | **First-party counters; retire Plausible.** Keep Cloudflare's free traffic dashboard alongside. ✅ shipped `bfb1ade` — the site now loads no third-party analytics script at all, and the Stats tab answers which events land. |
| Bulk extraction | **Build it** — bulk paste → draft queue → human approval. Never auto-publish. |
| Starting order | **Housekeeping first (C1–C3), then the card rebuild (A1).** |

Consequences worth noting:
- **B3 changes shape**: it is now *build counters + retire Plausible*, not *make Plausible work*. The nine Plausible goals (previously item 1.4) are **cancelled** — don't register them.
- **C3 (OG image) gets more urgent**, since it's in the first batch and it's what makes shared links stop previewing as a grey box.
- **B4 depends on C10** (`effort` tuning) and benefits from the content cap — do the cost measurement as the first step of that build, not after it.

The reasoning behind each is below, kept because the *why* matters more than the *what*.

### 1. Sober is not a category — even with multi-select

Your multi-category request (B2) looks like it solves the Sober filter. It doesn't, and the reason is worth 30 seconds:

Vibe filters combine with **OR** — picking Nightlife + Music means "show me either." If Sober were just another tag, picking Nightlife + Sober would return *all nightlife (bars included) plus all sober events*. The one thing a sober user actually wants — **sober nightlife** — is the one result that combination can't express, because Sober needs to combine with **AND**.

So: `tags[]` for categories (B2), plus a separate `alcohol_free` boolean with its own toggle sitting apart from the chips. Fitness genuinely is a category and rides along with B2 for free.

One rule for extraction: only set `alcohol_free` on an **explicit** signal ("dry", "sober", "alcohol-free", "no bar"). A page not mentioning alcohol is not evidence. Guessing optimistically here sends someone in recovery to a bar — the only failure mode in this project that hurts a person.

### 2. Admin analytics vs. the privacy stance — and what to do about Plausible

You have no behavioral data visible to you, and that's partly a deliberate choice biting back: `analytics.js` sends **categories only, never event IDs** — there's a test asserting the share token never leaks into a prop. That decision is why Plausible can tell you "40 saves happened" but never "which event got saved."

**Recommendation: build first-party counters and drop Plausible.** A tiny `event_stats` table (event_id, saves, skips, detail_opens, ticket_clicks) plus an aggregate daily rollup gives you exactly the questions you actually have — *which events land, which vibes convert, what's dying in the stack* — with no third-party script, no per-visitor identity, and no monthly fee. Plausible is a paid product after the trial (~$9/mo) and structurally can't answer the per-event question anyway.

**On Cloudflare:** keep it, but know what it is. Cloudflare's traffic dashboard is free and comes from proxying alone — pageviews, countries, bandwidth, threats. It cannot see swipes, saves, or shares. So it complements first-party counters rather than competing with them. One trap: if you enable Cloudflare **Web Analytics** (the RUM beacon), our CSP will silently block it — `script-src` doesn't allow `static.cloudflareinsights.com`.

So the three-way answer is: **Cloudflare for traffic (free, keep) · first-party counters for behavior (build) · Plausible retired (saves ~$9/mo and can't do the job).**

### 3. Bulk extraction — the numbers moved

You passed on this at ~$0.06/URL, which was the right call on those numbers. Three things change it:

| Lever | Effect |
|---|---|
| **Batch API** | **50% off**, async (usually under an hour). Bulk URL drops are *exactly* the async use case — you paste 20 links and come back to a review queue. |
| **Cap fetched page size** | The 26K input tokens are mostly page boilerplate, not event data. `web_fetch`'s `max_content_tokens` should cut that hard. Needs testing — too aggressive and we truncate the details we came for. |
| **Prompt caching** | Honestly marginal here (~$0.004/URL). The system prompt is the only stable prefix; the page is unique every time. Worth switching on, not worth planning around. |

Rough per-URL, Sonnet 5, after intro pricing ends 31 Aug 2026:

- Today, unoptimized: **~$0.11**
- Batch only: **~$0.055**
- Batch + content cap: **~$0.025**

At 50 events/week that's about **$5–7/month** instead of $24. Manual entry is still free, and I'd keep it as the primary path for the sources extraction can't reach anyway (vegas.com is JS-rendered; Instagram and TikTok are login-walled — both confirmed, not assumed). The realistic pitch is *extraction handles the easy 60%, you hand-enter the rest.*

**Model stays Sonnet** per standing policy — Opus would be roughly 3× for no benefit on a task this well specified.

---

## D. Your additions

<!-- Add anything here. -->
