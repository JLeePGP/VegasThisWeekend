# VegasThisWeekend — orientation

Mobile-first Las Vegas event discovery. Swipe, save, share by link. No accounts, no
cookies, free in v1. Owner: John (GitHub: JLeePGP).

**This file is a router, not a manual.** Read only what the task needs.

| If you're doing this | Read |
|---|---|
| Anything at all | this file |
| Picking up work / seeing what shipped | `BACKLOG.md` — session-close entry is at the top |
| Cloudflare, R2, backups, DNS, the proxy secret | `OPERATIONS.md` |
| Setup, architecture, analytics, design rationale | `README.md` |
| Nothing | don't preload the others "for context" — they are long |

## Status as of 30 Jul 2026

**Live and working.** Site `https://vegasthisweekend.com`, API
`https://api.vegasthisweekend.com`, 10 real events, 293 tests passing.

**John's current phase is not building.** He is adding events and getting the app in front
of people. Do not start feature work unless he asks — if he reports something broken while
doing that, fix it; otherwise the backlog is paused on purpose.

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

Cost and performance estimates here have been wrong more often than right. Measure.
