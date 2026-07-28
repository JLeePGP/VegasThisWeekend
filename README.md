# VegasThisWeekend

Mobile-first Las Vegas event discovery. Open it, swipe through what's on, save what looks
good, share it with your group. No account, no planning session.

**Phase 1 (this build): the consumer app.** Swipe stack, filters, saved list, share links,
insider tips — running against placeholder events.
**Phase 2 (next): the admin panel** — paste a URL, Claude extracts the event, John confirms.

---

## Status

| Piece | State |
|---|---|
| Swipe stack, filters, saved list, share links, insider tips | Built and verified in-browser |
| Backend API + 62 tests | Passing |
| Event data | **Placeholder.** Fictional venues, flagged `is_sample` |
| Admin panel / AI URL extraction | Phase 2, not started |
| Eventbrite integration | Config placeholder only |
| Deployed | No — Railway/Netlify accounts not yet created |

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

### Tests

```bash
cd backend && .venv/Scripts/python -m pytest tests -q      # 62 tests
```

---

## How it fits together

```
React (Vite) ──HTTPS──> FastAPI ──> PostgreSQL
   Netlify               Railway      Railway
```

```
backend/
  app/
    main.py          app wiring, CORS, rate limiting
    models.py        Event, InsiderTip, ShareList
    schemas.py       request/response contracts
    enums.py         the closed vocabularies clients may send
    timewindow.py    Vegas-local date logic  <- read this one first
    tips.py          matching curated tips onto events
    routers/         events.py, share.py
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

---

## Deploying

Neither account exists yet. When they do:

**Railway (API + Postgres)** — root directory `backend/`, add the Postgres plugin, and set:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | injected by the Postgres plugin |
| `CORS_ORIGINS` | `https://vegasthisweekend.com` |
| `ADMIN_TOKEN` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ANTHROPIC_API_KEY` | Phase 2 |
| `EVENTBRITE_API_KEY` | when sourced |

`Procfile` holds the start command. Setting `ENVIRONMENT=production` also switches off
`/docs` and `/openapi.json`.

**Netlify (frontend)** — base directory `frontend/`, build `npm run build`, publish `dist`.
Set `VITE_API_BASE_URL` to the Railway API origin. `netlify.toml` covers the SPA redirect
so `/s/<token>` resolves; `public/_headers` carries the security headers.

**After the API origin is known**, update `connect-src` in `frontend/public/_headers` to
match it, and `img-src` to the R2 bucket domain. The CSP currently names
`api.vegasthisweekend.com` and `images.vegasthisweekend.com` as placeholders.

**DNS (Namecheap)** — apex + `www` to Netlify, and a subdomain to the Railway API.

---

## Known gaps

- **`create_all` builds the schema, there are no migrations.** Fine while the shape is
  settled and the data is disposable; Alembic should land before the admin panel starts
  changing tables under live data.
- **Offset pagination** can skip or repeat an item if an event expires mid-scroll. The
  client dedupes by id, so the visible symptom is at worst a slightly short page.
- **Rate limiting is in-process**, so limits are per-instance. Fine at one instance; a
  second one needs shared storage.
- **"Return visits" is deliberately not instrumented** — cookieless analytics and no
  accounts means there is no honest way to measure it until v2 brings accounts.
