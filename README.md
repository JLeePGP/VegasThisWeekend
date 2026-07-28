# VegasThisWeekend

Mobile-first Las Vegas event discovery. Open it, swipe through what's on, save what looks
good, share it with your group. No account, no planning session.

**Phase 1: the consumer app.** Swipe stack, filters, saved list, share links, insider tips.
**Phase 2: the admin panel** — paste a URL, Claude drafts the event, John confirms and saves.

---

## Status

| Piece | State |
|---|---|
| Swipe stack, filters, saved list, share links, insider tips | Built and verified in-browser |
| Admin panel: manual entry, event list, edit, tips | Built and verified in-browser |
| AI URL extraction | Built; **needs `ANTHROPIC_API_KEY` to run** |
| Image mirroring to Cloudflare R2 | Built; **needs R2 credentials to run** |
| Backend API + 161 tests | Passing |
| Schema migrations (Alembic) | In place; `create_all` retired |
| Event data | **Still placeholder.** Fictional venues, flagged `is_sample` |
| Eventbrite integration | Config placeholder only |
| Deployed | No — Railway/Netlify accounts not yet created |

Both credential-gated features degrade rather than break: without an Anthropic key the
admin panel is manual-entry only and says so; without R2 the event saves and keeps its
generated poster.

Every seeded event is invented and every venue name is fictional. While any sample event
is in the database the API reports `sample_data: true` and the app shows a banner saying
so, which means fabricated listings cannot quietly pass as real ones. Delete the samples
and the banner disappears on its own.

---

## Running it locally

Two processes. Backend first.

### Backend — http://127.0.0.1:8000

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/python
cp .env.example .env
.venv/Scripts/python seed_sample_events.py
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Interactive API docs at `/docs` (development only — disabled in production).

Re-seeding later: `python seed_sample_events.py --reset`. Slots are computed relative to
today, so the sample data is always "this coming weekend" whenever you run it.

### Frontend — http://localhost:5173

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The dev server also binds to your LAN, so you can open it on a real phone — which is the
only honest way to judge a swipe interaction.

### Admin panel — http://127.0.0.1:5174

Runs on your machine only; it is never deployed. It talks to whichever API
`VITE_API_BASE_URL` names — the local backend while you're testing, the Railway origin
once you're seeding real events.

```bash
cd admin
npm install
cp .env.example .env
npm run dev
```

Sign in with the `ADMIN_TOKEN` from `backend/.env`. It is stored in the browser, not in
a file, so it never lands in the repo.

**To switch on AI extraction**, put your key in `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

An API key is **not** the same as a Claude Pro subscription — Pro covers claude.ai, while
API usage is billed separately against credits on your Anthropic Console account. Create
the key at console.anthropic.com.

Extraction runs on **Sonnet 5** (`ANTHROPIC_MODEL`). This is structured field-pulling with
a few judgment calls, not long-horizon agentic work, so Sonnet tier is the right fit at
roughly a third of Opus 5's cost. `thinking` is set to adaptive explicitly rather than
left to the default, because that default differs by model — on Sonnet 4.6, omitting it
means no thinking at all, which would quietly remove reasoning from the date arithmetic.

Restart the API. The panel's header badge flips to `extraction on`. Without it, the URL
box is disabled and the form below works exactly as normal.

**To switch on image mirroring**, create an R2 bucket and fill in all five `R2_*` values
in `backend/.env`. Until then events keep the client-side generated posters.

### Tests

```bash
cd backend && .venv/Scripts/python -m pytest tests -q      # 161 tests
```

### Migrations

Alembic owns the schema; the app no longer creates tables at boot, and Railway runs
`alembic upgrade head` on every deploy via the `Procfile`.

```bash
cd backend
.venv/Scripts/alembic upgrade head                          # apply
.venv/Scripts/alembic revision --autogenerate -m "what changed"
```

### A temporary public URL (for testing on a real phone)

A LAN address won't do: `http://192.168.x.x` is not a *secure context*, so the native
share sheet and the clipboard API are both unavailable. Tunnelling an https origin is what
makes the share flow testable on a phone.

Three terminals:

```bash
# 1. API
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000

# 2. Production build, served with /api proxied to the API so it's all one origin
cd frontend
VITE_API_BASE_URL=/api npm run build      # PowerShell: $env:VITE_API_BASE_URL="/api"
npm run preview -- --port 4173

# 3. Public https URL
cloudflared tunnel --url http://127.0.0.1:4173
```

Because everything is one origin, CORS never enters into it, and share links are built
from the tunnel origin so they work for whoever you send them to.

**This exposes your local app and API to the public internet** for as long as the tunnel
runs. The quick-tunnel URL is random and unlisted, the data is fake, and the endpoints are
rate limited — but stop the `cloudflared` process when you're done. The URL changes every
time you restart it. Note also that `public/_headers` is a Netlify feature, so the CSP is
*not* applied on a tunnelled preview.

---

## How it fits together

```
React (Vite) ──HTTPS──> FastAPI ──> PostgreSQL          Admin (Vite)
   Netlify               Railway      Railway            your machine
                            ▲                                 │
                            └─────── bearer token ────────────┘
```

The admin panel is a separate app that is never deployed. It runs locally and writes to
the live API, so the `/admin` routes are reachable from the internet and the token — not
network location — is what guards them.

```
backend/
  app/
    main.py          app wiring, CORS, rate limiting
    models.py        Event, InsiderTip, ShareList
    schemas.py       public request/response contracts
    schemas_admin.py admin contracts (local times cross this boundary)
    enums.py         the closed vocabularies clients may send
    timewindow.py    Vegas-local date logic  <- read this one first
    tips.py          matching curated tips onto events
    auth.py          admin bearer token
    extraction.py    Claude → a draft event
    recurrence.py    a residency → one row per night
    duplicates.py    "have I already added this?"
    images.py        mirroring images to R2 (and the SSRF guards)
    routers/         events.py, share.py, admin.py
  alembic/           schema migrations
  seed_sample_events.py
  tests/

frontend/src/
  api.js             every network call
  format.js          Vegas-time rendering
  constants.js       filter vocabularies (mirror of the backend enums)
  store/             saved events (localStorage), toasts
  hooks/useEvents.js paging and filtering
  components/        SwipeStack, EventCard, Poster, FilterBar, EventSheet, screens
```

### Decisions worth knowing

**Everything happens in Vegas time.** A visitor planning from New York at 1am Eastern is
still asking about Vegas Thursday, so both the query and the display are pinned to
`America/Los_Angeles` rather than the device clock.

**A night belongs to the day it started.** The listing day rolls over at 5am, not
midnight. A party running Friday 10pm to Saturday 3am is a Friday night, and a Thursday
10pm party is *not* part of the weekend just because it spills past midnight. 5am is also
the safe choice across DST — unlike 1am it never happens twice, and unlike 2am it never
fails to happen. Consequence: a genuine multi-day festival wants one row per day, which is
also what makes sense on a swipe card.

**Filtering is on start time, not overlap.** Directly out of the rule above.

**Events are never deleted, only flagged inactive**, and anything past its end time drops
out of the stack automatically.

**No image is a supported state.** Cards render a poster generated from the event's own id
— colours from its category, composition from a hash. Real events point `image_url` at
Cloudflare R2.

**Local dev uses SQLite, production uses Postgres.** Column types are deliberately
portable so the same models serve both, with no dialect-specific code.

**The model never does timezone arithmetic.** Extraction returns naive Vegas wall-clock
strings and the admin form posts the same, because `datetime-local` inputs emit exactly
that format. The single conversion to UTC happens server-side in code that has tests —
not in a model's head, and not in a browser.

**Extraction returns a draft, never a row.** Nothing Claude produces reaches the database
without passing through the review form. Fields the model had to guess at are returned in
`uncertain_fields` and highlighted in the form rather than silently accepted.

**Page content is data, not instructions.** A venue page is untrusted input that could
contain text aimed at the model. Three independent controls: the output schema constrains
the shape, URL fields are checked against a scheme allowlist, and a human reviews every
draft. None of the three is sufficient alone.

**A residency is stored as the nights it actually runs.** The swipe stack, the date
filters and the share snapshots all assume concrete rows, so recurrence is expanded at
save time rather than modelled as a rule. Occurrences are generated in wall-clock time, so
a 10pm night stays at 10pm across a DST change.

**Duplicate detection warns, never blocks.** Two genuinely different events can share a
venue and a start time — two rooms, two stages — so a collision returns 409 with what it
hit and the decision stays with John.

### Security posture

- No secret ever reaches the browser; all external calls go through the backend.
- CORS is locked to exact origins, no wildcards, credentials off.
- Every client filter is an enum — a freeform string is a 422, not a query.
- Rate limits per the spec: events 100/min, share creation 10/min.
- Results are always paginated; no endpoint dumps the catalog. Ids are random, not
  sequential, so it cannot be walked.
- Share lists hold event ids, a random token and an expiry — no user identity, no IP.
- Saved events live in `localStorage` and are never sent anywhere except as ids when you
  explicitly create a share link.
- CSP, `X-Frame-Options`, and friends ship in `frontend/public/_headers`.
- Client IPs are used transiently as rate-limit keys and are never stored or logged.
- Admin routes require a bearer token, compared in constant time. An unset `ADMIN_TOKEN`
  disables them with a 503 rather than leaving them open.
- The admin token lives in the browser's `localStorage`, never in a committed file.
- Image mirroring is a server-side fetch of an attacker-influenced URL, so every hop is
  checked to resolve to a public address, redirects are followed by hand rather than by
  the HTTP client, the content type is allowlisted and the body is capped mid-stream.
  Cloud metadata endpoints and private ranges are refused — see `tests/test_extraction.py`.

---

## Deploying

Neither account exists yet. When they do:

**Railway (API + Postgres)** — root directory `backend/`, add the Postgres plugin, and set:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | injected by the Postgres plugin |
| `CORS_ORIGINS` | `https://vegasthisweekend.com,http://localhost:5174` |
| `ADMIN_TOKEN` | a **different** value from your local one — `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ANTHROPIC_API_KEY` | for URL extraction |
| `R2_ACCOUNT_ID` … `R2_PUBLIC_BASE_URL` | all five, for image mirroring |
| `EVENTBRITE_API_KEY` | when sourced |

`localhost:5174` is in the production CORS list on purpose: the admin panel runs on your
machine and writes to the deployed API. CORS is not the control here — the bearer token
is; this only stops the browser refusing the request before it is sent.

`Procfile` runs `alembic upgrade head` before starting the server, so a deploy applies
migrations. Setting `ENVIRONMENT=production` also switches off `/docs` and `/openapi.json`.

**Netlify (frontend)** — base directory `frontend/`, build `npm run build`, publish `dist`.
Set `VITE_API_BASE_URL` to the Railway API origin. `netlify.toml` covers the SPA redirect
so `/s/<token>` resolves; `public/_headers` carries the security headers.

**After the API origin is known**, update `connect-src` in `frontend/public/_headers` to
match it, and `img-src` to the R2 bucket domain. The CSP currently names
`api.vegasthisweekend.com` and `images.vegasthisweekend.com` as placeholders.

**DNS (Namecheap)** — apex + `www` to Netlify, and a subdomain to the Railway API.

---

## Known gaps

- **Login-walled sources cannot be fetched by anything.** Instagram and Facebook posts
  will not resolve server-side, by Claude or by us. That is what the "paste text instead"
  box is for — it is the only path for a real slice of the PRD's stated sources.
- **Extraction has never run against a live page.** The code path is built and unit
  tested against mocked responses, but no `ANTHROPIC_API_KEY` has been configured yet, so
  its behaviour on a real Eventbrite or venue page is unverified.
- **Extraction costs money per paste** — roughly **$9/month** at 30–50 events a week on
  Sonnet 5 (~$14 once its introductory pricing ends on 31 Aug 2026). Opus 5 would be ~$23
  for no benefit on this task. `ANTHROPIC_MODEL` is configurable.
- **`effort` is the next cost lever and is untuned.** It defaults to `high`; `medium`
  would likely cut thinking tokens with no quality loss on a task this well specified.
  Deliberately left alone until a live extraction can be measured — guessing at it
  without data would just be a different kind of wrong.
- **A series is generated once.** Editing a residency means editing each night. Fine at
  26 occurrences; it would want a real recurrence model before it wants a hundred.
- **Offset pagination** can skip or repeat an item if an event expires mid-scroll. The
  client dedupes by id, so the visible symptom is at worst a slightly short page.
- **Rate limiting is in-process**, so limits are per-instance. Fine at one instance; a
  second one needs shared storage.
- **"Return visits" is deliberately not instrumented** — cookieless analytics and no
  accounts means there is no honest way to measure it until v2 brings accounts.
