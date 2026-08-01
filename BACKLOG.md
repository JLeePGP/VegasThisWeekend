# Backlog

Consolidated 30 Jul 2026 — John's feedback merged with the 29 Jul audit.

---

## Priority order — agreed 1 Aug 2026

The newsletter is the top priority; sourcing is the constraint underneath everything.

| # | What | Effort | State |
|---|---|---|---|
| 1 | Update 1 deployed, verified in production | — | ✅ done, `cebaa9c` |
| 2 | **Admin Newsletter tab** — see the list, export a window, remove an address | S | ✅ done |
| 3 | **Mailing address for the newsletter footer** — John's errand, has a lead time | — | ⬜ |
| 4 | **Buttondown account + draft-issue script** — query the week's events, emit markdown | M | ⬜ |
| 5 | **Events, hard — recurring first** | ongoing | ⬜ |
| 6 | **PWA** — manifest, icons, service worker | S–M | ⬜ |
| 7 | **Desktop layout** — breakpoints, header nav, sidebar filters, two-column detail | M | ⬜ |
| 8 | **Edge metadata injection** for `/e/:id` — makes desktop findable, fixes link previews | S | ⬜ |

### Why this order

**Sourcing is doing the quiet work in it.** A weekly issue needs three good things every
week, forever, and 31% of sessions still reach the end of the catalog. The newsletter
raises sourcing pressure rather than relieving it — which is exactly the failure that
killed the five other projects people described at launch. **Recurring events are the
lever**: one entry expands to twelve weeks through the recurrence code that already
exists, where a one-off costs the same effort for one row.

**Don't build sending infrastructure for an empty list.** Capture went live today with
zero subscribers. The list fills first.

### #6–8, the surface work, in the order they pay off

- **PWA is not cosmetic.** iOS evicts localStorage after ~7 days of no visits, which is
  the actual cause of saved events vanishing — the complaint behind the two people who
  asked for accounts. Installed web apps are exempt from that. It also unlocks iOS web
  push (16.4+) without an app store.
- **Desktop layout is cheap** — there are currently zero layout media queries, so there
  is nothing to unpick, only breakpoints to add. The shell (`100dvh` + inner scroll)
  becomes document scroll, `TabBar` becomes header nav, filters become a sidebar.
- **Desktop's real problem is arrival, not layout.** People reach desktop from Google,
  and the app is client-rendered. Per-event URLs now exist, so the cheap fix is a Netlify
  Edge Function injecting `<title>`/OG tags for `/e/:id`. A framework migration would do
  it properly and costs weeks — not worth it at 14 events.

**Native app: not on this list.** A Capacitor wrapper is days of work plus $99/yr and
review risk under Apple's minimum-functionality guideline, for something the PWA already
gives away free. A React Native rewrite ports about 500 of 1,900 frontend lines — every
screen is a rewrite. Revisit only if push becomes the retention mechanism, and note the
newsletter is already that.

---

## Newsletter — what has to be true before issue one

| | |
|---|---|
| Capture | ✅ live, `POST /subscribers`, own table, no third-party form |
| Getting addresses out | ✅ Admin → **Newsletter** tab |
| Consent record | ✅ every row stores `created_at` and which screen it came from |
| Provider | ⬜ **Buttondown** recommended — usable free tier, plain-text friendly, no growth cruft |
| Mailing address | ⬜ **CAN-SPAM requires a physical address in every issue.** PO box or virtual mailbox; has a real-world lead time |
| Draft script | ⬜ query the week's events → markdown issue. This is the loop that makes per-issue cost near zero |
| Cadence | Weekly, day not yet committed — **the app deliberately promises no day and no first-issue date**, so waiting for signups costs nothing |

**The export discipline, and why the tab works the way it does.** Unsubscribes live with
the provider; this table never hears about them. Exporting the whole list a second time
would re-add everyone who opted out — the one genuinely unpleasant mistake available
here. So the tab exports a **window** (`since` a date), records the export date locally,
and defaults the next export to it. That solves it with no schema column and no state to
keep in sync. Most providers do keep an unsubscribed address unsubscribed on re-import,
but verify it for whichever you pick rather than trusting it — the window makes it moot.

**Addresses are masked in the panel** (`jk••••••••@gmail.com`) with reveal per row. The
realistic leak here is a screen share or a screenshot, not a breach.

---

## Update 1 shipped — 1 Aug 2026

**The swipe deck is gone.** Merged to `main` as `cebaa9c` and verified in production.

### What shipped

| | |
|---|---|
| Listing | Day headers, chronological within each day. `SwipeStack`, `EventCard`, the queue model, dismissals, the action row, the swipe hint and the immersive shell are all deleted |
| Rows | Thumbnail, time, name, neighbourhood, price, save. One `EventRow` now serves the listing, Saved and shared lists |
| Detail | Its own route, `/e/<id>`, bounded hero. `EventSheet` deleted |
| Video | Play button on the detail page only, full-screen at native 9:16. `Poster` no longer renders video at all |
| Email | `POST /subscribers`, own table, migration `a1f6c30b74e2`. Capture at the end of the listing and on Saved |
| Ordering | `_lead_event_id` reverted — it put a promoted row under the wrong day header |

### Decisions taken while building

- **Email goes to our own API, not a provider's embed.** An embed would have loaded a
  third-party frame and handed that company every visitor's IP, undoing `d299820`. Signing
  up twice is a no-op whose response is identical to a first signup, so the endpoint
  cannot be used to test whether an address is on the list.
- **Detail is a route, not a taller sheet.** It survives a refresh, can be sent to
  someone, and is the only shape that could ever be indexed (A5).
- **`skip` and `stack_exhausted` are retired**, replaced by `list_end`, plus `video_play`
  and `subscribe`. Historical rows are untouched and still reported.
- **Save rate is now blank for anything after 1 Aug.** It needed an explicit no, which a
  swipe left was and scrolling past a row is not. Left alone it would have computed
  saves/(saves+0) and shown a flawless rate for every event ever saved. The Stats tab
  hides the swipe-era tiles once a range contains none of that data.

### Verified

- 342 backend tests passing; frontend and admin bundles both build
- Migration applied to the local SQLite database and the schema checked
- Against a locally running API: chronological order holds with a video event present,
  `GET /events/{id}` 200s, and signup normalises case, is idempotent, and 422s junk
- Every route rendered to static markup without crashing; day grouping honours the 5am
  rollover (a 9pm Aug 1 event files under Aug 1), and rows carry no venue, hook or video

**Verified in production after the merge:** signup returns 202, the listing opens with a
10am event instead of the promoted 7:30pm one, `/e/<id>` deep links resolve on the apex
domain, and `/health` reports `production`. John checked the site on desktop and mobile
before the merge.

One artefact: verifying signup inserted `deploy-probe@example.com` into the production
table. Remove it from the Newsletter tab before the first export.

### Left alone deliberately

Date range filter, venue filter, accounts, user-submitted events, insider-tip reshape,
share selection (cut), volume on video. All still deferred with the reasons below.

---

## Session close — 31 Jul 2026

**The swipe interaction is being removed.** That is the headline, and everything below
follows from it. Read this section before planning anything.

### What launch feedback actually said

25 people commented. The signal was not ambiguous:

- **8 of 25 asked for a list view, unprompted.** Very few liked the card stack. One was a
  real Las Vegas friend, not an anonymous account.
- **5 said they had built something similar and quit** — because sourcing and maintaining
  curation over months got too hard. That is the failure mode of this whole category, and
  it is a bigger threat to this project than any UI decision.
- 2 asked for accounts. Deferred — see below.
- People were drawn to **consolidation of events that are not the usual Strip hype**, not
  to video, and not to the interaction. The catalog is the product.

### Why swipe was wrong, beyond the vote count

Swipe suits an effectively infinite pool where comparison does not matter. A weekend of
events is a **finite, time-ordered, comparable set** — the real question is "what else is
on at 9pm?", and a card stack physically prevents answering it.

### Usage data behind these calls (30–31 Jul, 689 sessions)

Two days, launch spike, includes John's own testing — directional only.

| metric | count | per session |
|---|---|---|
| save | 517 | **0.75** |
| detail_open | 231 | 0.34 |
| stack_exhausted | 215 | **0.31** |
| website_click | 83 | 0.12 |
| ticket_click | 24 | **0.035** |
| share_create | 3 | 0.004 |

- **31% of sessions exhausted the catalog.** The thin catalog is measured, not assumed.
- **Saving works** — keep it. It is the only interaction that survives the pivot.
- **Sharing is dead.** "Choose which events to share" is cut from the roadmap, not
  refined. 3 uses in 689 sessions.
- **Ticket clicks are 3.5%, venue-site clicks are 3.5× higher.** People discover here and
  transact elsewhere, which is why ticketing affiliate is not a viable path.

### Update 1 — agreed scope

List-only. This is a **deletion**, not another mode.

- Remove `SwipeStack.jsx`, swipe gestures, the deck/queue model, dismissals, "That's
  everything", the floating action row and the swipe hint
- Single list view: day headers (weekday + date), chronological within each day
- Rows carry **thumbnail, time, name, neighbourhood, price, save**. No hook — it read as
  Eventbrite and the curation lives in *which* events are listed, not in row copy
- Venue moves to the detail view; venue filtering comes later
- Tap a row → detail. Details are the page; the **image** is a bounded hero
- Video only via a **player button on the detail view**, opening full-screen at native
  9:16. Never cropped, never a faded background, never in a row
- **Email capture** at the end of the list and on the Saved screen
- Date range filtering **not** in this update — existing today/weekend/all stays

Two consequences of the pivot that are easy to miss:

1. **The empty-deck overlap bug disappears on its own.** It was the action row covering
   the empty state. No action row, no bug.
2. **`_lead_event_id` in `routers/events.py` becomes wrong.** Promoting a video event out
   of chronological order was right for a card stack; in a day-grouped list it breaks
   both the grouping and the time ordering. Revert or gate it as part of Update 1.

### Strategy — the app is the engine, the newsletter is the product

Monetisation is the open question and the app monetises last. The reframe John landed on:

**The catalog labour is identical whichever surface it feeds.** The app needs far more
traffic before anything pays; a local newsletter monetises at audience sizes an app cannot
touch, and it fixes retention — email arrives whether or not someone remembers the app.

The loop that makes this defensible: structured catalog → drafted issue is a query, not
research. Per-issue cost near zero is the direct counter to the thing that killed those
five other projects.

Decisions taken:

- **Email before SMS.** SMS needs 10DLC carrier registration, costs per message, and
  sponsors do not buy it. Revisit only for opt-in "tonight only" alerts.
- **Audience is locals, not tourists.** Tourists churn 100%, which is fatal for a weekly.
  "Not the same old Strip hype" was already written for locals.
- **Let a thin week be a short issue.** Quota-driven padding is why curator newsletters
  fall flat — three good things beats ten with seven fillers.
- **Build no newsletter infrastructure.** Capture emails in the app, send from Beehiiv or
  Buttondown's free tier, script a draft issue from the database. Six weekly issues, then
  judge on open rate and replies.

### Deferred, with reasons

- **Accounts** — 2 of 25. Conflicts with the no-accounts/no-cookies stance. Note the real
  problem may be storage durability, not a missing feature: saves live only in
  localStorage and iOS evicts it after ~7 days of no visits. Cheaper rungs first: a PWA
  manifest (there is none — someone already tried adding the site to their home screen by
  hand), then Upcoming/Past grouping on Saved, then a recovery link. Accounts last.
- **User-submitted events** — too much admin today, but it is the cheapest known attack on
  the maintenance problem that killed the other five projects. Luma tolerates open
  submission because events land on the submitter's own calendar; here a single curated
  feed *is* the product, so submissions need triage. Lighter path: a public form that
  feeds the existing `extraction_drafts` queue, so approving is clicks rather than
  re-entry.
- **Insider tips** — the venue-matching shape was wrong; tips are often event-specific.
  Replace with a plain text field on the event, filled in during entry. Additive
  migration. The `insider_tips` table (0 rows) can simply stop being used.
- **Share selection** — cut outright, see the data above.
- **Date range filter**, **venue filter**, **volume on video** — later, none urgent.

### After Update 1: events, hard

31% catalog exhaustion says sourcing is the binding constraint. No layout fixes a thin
catalog. Extraction, bulk extraction and recurrence already exist and are the leverage —
anything that lowers per-event cost is worth more than a feature.

### What shipped this session

| Commit | What |
|---|---|
| `236a4b1` | TikTok videos mirrored by downloading with yt-dlp, not by resolving a URL |
| `0825619` | Feed leads with a video card, rotating by listing day — **now obsolete, see above** |
| `d299820` | `img-src`/`media-src` narrowed to the R2 domain |
| `bbbd21f` | Nightly database backup to a private R2 bucket |
| `2ebfcb8` | Backup actions pinned to Node 24 majors |

- **OPERATIONS §1 is complete.** R2 live, all 14 events serving both media fields from
  `media.vegasthisweekend.com`, CSP tightened and verified at the edge. The site now
  contacts zero third-party hosts.
- **Backups exist for the first time.** Railway gates snapshots behind a paid plan, so
  `scripts/export_data.py` writes every row to JSON nightly into `vtw-backups` (private,
  separate token from the public media bucket). Verified by downloading and parsing a real
  upload. It is a data export, not a `pg_dump` — restoring means migrating to the recorded
  alembic revision and loading rows.
- Still open in OPERATIONS: §2 Web Analytics toggle, §3 edge cache rule, §4 proxy secret
  (most dangerous — do it in a quiet window, never alongside a feature ship).

### Staging environment — new, use it

| | |
|---|---|
| URL | https://staging--vegasthisweekend.netlify.app |
| Branch | `staging` — Netlify branch deploys are enabled for it |
| CORS | that origin is in Railway's `CORS_ORIGINS` |

Two gotchas that already cost time:

- **Netlify skips builds with no frontend change** (base directory is `frontend/`), and
  reports it as "Canceled". A backend-only commit shows a cancelled deploy and that is
  correct behaviour, not a failure.
- **Per-PR deploy previews cannot work** — their URLs vary and CORS is exact-match, so
  they are switched off deliberately. One long-lived `staging` branch is the sandbox.

Staging runs against the **production API and database**. Share links created while
testing are real rows, and test traffic nudges the real counters.

### State at close

- 323 backend tests passing; working tree clean
- `main` at `2ebfcb8`, `staging` branched from it at `94dec78` (an empty commit)
- 14 live events, 47 rows total. No sample data
- Update 1 is agreed but **not started** — no frontend code has been written

---

## Session close — 30 Jul 2026

Session ended here. John moves to **adding events and finding users**; the build work
pauses.

### Links

| What | Where |
|---|---|
| Site | https://vegasthisweekend.com |
| API | https://api.vegasthisweekend.com |
| Admin panel | `cd admin && npm run dev` → http://localhost:5174 — local only, never deployed |
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
