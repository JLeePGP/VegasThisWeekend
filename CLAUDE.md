# VegasThisWeekend — orientation

Mobile-first Las Vegas event discovery. A day-grouped list of what's on: browse, save,
share by link. No accounts, no cookies, free in v1. Owner: John (GitHub: JLeePGP).

**This file is a router, not a manual.** Read only what the task needs.

| If you're doing this | Read |
|---|---|
| Anything at all | this file |
| Picking up work / seeing what shipped | `BACKLOG.md` — session-close entry is at the top |
| Cloudflare, R2, backups, DNS, the proxy secret | `OPERATIONS.md` |
| Setup, architecture, analytics, design rationale | `README.md` |
| Nothing | don't preload the others "for context" — they are long |

## Status as of 7 Aug 2026

**Live and working.** Site `https://vegasthisweekend.com`, API
`https://api.vegasthisweekend.com`, **9 upcoming events**, 400 tests passing, CI on every
push.

**The swipe deck is gone.** Update 1 replaced it with a day-grouped list after launch
feedback — 8 of 25 people asked for a list unprompted. If you find a reference to swiping,
a card stack, dismissals or `stack_exhausted` anywhere, it is stale and should be fixed
rather than followed. `BACKLOG.md` carries the reasoning.

**There is a desktop layout now, and it is one app.** Shipped 7 Aug. Width decides, never
the device — `useMediaQuery` plus a single `@media (min-width: 1024px)` block at the foot
of `app.css`, with components forking behind a boolean where the structure differs. Below
1024px nothing changed, and that is structural rather than incidental: every desktop rule
is inside that one media query. Do not add desktop styling anywhere else.

⚠ **The breakpoint is written down twice** — `DESKTOP_QUERY` in `constants.js` and the
media query in `app.css` — because a custom property cannot be used in a media query.
Change both or neither.

**Also shipped 1 Aug:** newsletter capture and an admin Newsletter tab, series editing,
recurrence patterns beyond weekly, per-event share previews via a Netlify edge function,
and the app is installable to the home screen.

**Sourcing is the binding constraint and it is getting worse** — 31% of sessions reached
the end of the catalog when there were 14 events, and there are now 9. No layout change
improves that; the desktop work made it more visible, not better. Read the session-close
entry at the top of `BACKLOG.md` before planning anything.

Five things are built but switched off, all needing dashboard access John has and you
don't: R2 credentials, the Cloudflare cache rule, the Web Analytics toggle, the proxy
shared secret, and backups. `OPERATIONS.md` has each one with the check that proves it
worked. Don't re-derive or re-plan these; they're written down.

## Standing constraints — these are not negotiable

- **Never use Opus for anything this project runs.** Extraction is `claude-sonnet-5`. If
  you think something needs a pricier model, state the cost at expected volume first and
  let John decide. (Measured: $0.13–$0.35/URL, ~$5–7/month.)
- **The Anthropic API key is for admin-panel URL extraction only.** Nothing else.
- **Align before building.** Ask clarifying questions on anything new before writing code.
- **Never print secrets into the transcript.** They live in
  `Desktop/Vibe_Coding_Projects/Keys/`, outside the repo.
- **`subscribers` is the only table holding personal data**, and the newsletter is the one
  deliberate exception to "no accounts, no cookies". Nothing about a signup request is
  stored beyond the address and which screen it came from — no IP, no user agent. Do not
  add a column that changes that, and remember a database export now contains real email
  addresses: private backup bucket only.
- Production and local `ADMIN_TOKEN` values are different.
- Migrations are **additive-only** (expand-then-contract). A `downgrade` once wiped a dev
  database. There is no confirmed production backup yet.

## Things that will waste your time if you don't know them

- **The admin panel is never deployed.** `cd admin && npm run dev` →
  **http://localhost:5174**. Not `127.0.0.1` — same machine, different origin, and only
  `localhost` is in the production CORS allowlist. Getting it wrong reports "Can't reach
  the API" while the API is perfectly healthy.
- **Everything is Vegas-local time** with a 5am listing-day rollover.
- **`sober` is not a vibe.** It's `Event.alcohol_free`, because vibe filters OR together
  and "sober nightlife" would be the one query the filter couldn't express.
- **Event tags are additive.** Filtering on the tag table alone hides events that have no
  tag rows. The query ORs the primary `vibe` column with the tag table for that reason.
- **Two proxies sit in front of the API** (Cloudflare, then Railway). The socket peer is
  always `100.64.x.x`, never the visitor. Use `client_ip.py`.
- **CSP lives in `frontend/public/_headers`** and is enforced only in production, so a
  violation is invisible in dev. Cloudflare can inject scripts at the edge that never
  appear in this repo's HTML.
- **`admin/.env` is gitignored.** Editing it changes nothing in the repo.

## Verifying your own work

This project has a history of changes that looked right and did nothing — a dead CSS
selector, a link whose field was never serialised, a CSP that silently blocked every
video. Check the deployed thing, not the diff. `curl -s -D - -o /dev/null <url>`; `curl -I`
sends HEAD and FastAPI answers 405.

**There is no frontend test runner.** The 400 tests are all backend, and they stay green
through any amount of frontend breakage — never cite them as evidence a UI change works.
Drive a real browser against the deployed URL instead; `frontend/node_modules/playwright-core`
is already there and launches system Chrome with `{ channel: 'chrome' }`.

**Stub `/interactions` when you automate against staging or production.** Both talk to the
production API, so a scripted pass writes real counters into the data the roadmap is read
from. Assert on values read out of the page, not on numbers typed into the test — offsets
that were hardcoded in a test reported six false failures the first time the chrome grew.

Cost and performance estimates here have been wrong more often than right. Measure.
