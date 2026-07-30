# VegasThisWeekend

Mobile-first Las Vegas event discovery. Open it, swipe through what's on, save what looks
good, share it with your group. No account, no planning session.

**Phase 1: the consumer app.** Swipe stack, filters, saved list, share links, insider tips.
**Phase 2: the admin panel** — paste a URL, Claude drafts the event, John confirms and saves.

---

## Status

**Live as of 29 Jul 2026**, with one thing outstanding — see [BACKLOG.md](BACKLOG.md).

| Piece | State |
|---|---|
| API | ✅ live — `https://api.vegasthisweekend.com` (Railway) |
| Database | ✅ Postgres on Railway, migrations applied, **10 real events** |
| Website | ✅ live — `https://vegasthisweekend.netlify.app` |
| Website on the real domain | ⏳ DNS correct; **Netlify TLS certificate still provisioning** |
| Swipe stack, filters, saved list, share links, insider tips | ✅ built, verified in-browser |
| Admin panel: manual entry, list, edit, tips, duplicates, series | ✅ built, verified in-browser |
| Analytics (9 custom events) | ✅ shipped — **needs the goals registered in Plausible to display** |
| AI URL extraction | ✅ works; run live against real pages. Defeated by JS-rendered and login-walled sources — paste-text is the fallback |
| Backend API + 161 tests | ✅ passing |
| Schema migrations (Alembic) | ✅ in place, runs on deploy; `create_all` retired |
| Image mirroring to Cloudflare R2 | Built; **needs R2 credentials to run** |
| Eventbrite integration | Config placeholder only |

Where credentials are missing, features degrade rather than break: no Anthropic key means
the admin panel is manual-entry only and says so; no R2 means events save and keep their
generated posters.

**DNS** (all at Namecheap): apex `ALIAS → apex-loadbalancer.netlify.com`, `www CNAME →
vegasthisweekend.netlify.app`, `api CNAME →` the Railway target.

Production contains only real, hand-entered events — no sample data ever reached it. The
seed script and its fictional venues remain for local development. While any sample event
is present the API reports `sample_data: true` and the app shows a banner saying so, so
fabricated listings cannot quietly pass as real ones.

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

**One list, and it lives in [BACKLOG.md](BACKLOG.md)** — outstanding work, technical debt,
and what is blocked on which dashboard. Keeping a second copy here only guarantees the two
disagree.

Two things worth knowing while reading the code, since they shape it:

- **Login-walled and JS-rendered sources cannot be fetched by anything.** Instagram and
  TikTok will not resolve server-side, by Claude or by us, and vegas.com renders its event
  data client-side — measured, not assumed. That is what the "paste text instead" box is
  for; it is the only path for a real slice of the PRD's stated sources.
- **Extraction costs about $0.06 per URL**, measured live: ~26K input tokens for a real
  venue page. That is ~$14/month at 50 events a week on Sonnet 5's introductory pricing,
  ~$21 after 31 Aug 2026. Manual entry is free and is currently the primary workflow.
  `ANTHROPIC_MODEL` is configurable; **Opus is off the table for this project** — it would
  be ~$23/month for no benefit on a task this well specified.

---

## Analytics

Three of the PRD's four success metrics are interactions, not pageviews, so none of them
exist without custom events. These fire from `frontend/src/analytics.js`.

| Event | Props | Answers |
|---|---|---|
| `Swipe` | `direction` save/skip, `method` gesture/keyboard/button | Is anyone using it, and are they actually *swiping* |
| `Save` | `source` swipe/detail/shared_list, `vibe` | Events saved per session — is the content resonating |
| `Share Created` | `count`, `truncated` | Share links created |
| `Shared List Opened` | `count` | **Actual reach.** Links created is intent; this is spread |
| `Detail Opened` | `vibe`, `source` | Depth of interest past the swipe |
| `Tip Revealed` | `vibe` | Whether curating tips is worth the effort |
| `Stack Exhausted` | `reason` | Catalog too thin for the filters in use |
| `Filter Changed` | `date`, `vibes`, `prices` | Which vibes and price bands people reach for |
| `Ticket Clicked` | `vibe` | Closest thing to a conversion this app has |

`Swipe` and `Save` deliberately overlap on a right-swipe: `Swipe` measures engagement
volume, `Save` measures the saves metric, and keeping them separate means neither has to
be derived from the other in the dashboard.

**⚠️ Plausible needs each of these registered as a goal before it will display them.**
The events are recorded either way, but the dashboard shows nothing until you add them:
Plausible → Site Settings → Goals → Add goal → *Custom event* → type the name exactly as
written above. Miss this and it looks like the instrumentation is broken.

Two deliberate constraints in `analytics.js`:

- **Analytics can never break the app.** Every call is wrapped, so a blocked script, an
  ad blocker or a Plausible outage is a silent no-op rather than a crash mid-swipe. This
  is covered by a browser test that removes `window.plausible` entirely and confirms
  swiping and filtering still work.
- **Nothing identifying is sent.** Props carry categories and counts only — never event
  ids, never share tokens. A test asserts the share token appears in no prop, because
  leaking it would quietly undo the privacy stance that made Plausible the right choice.

**"Return visits" is deliberately not instrumented.** Cookieless analytics and no accounts
means there is no honest way to measure it until v2 brings accounts. The other three PRD
metrics are covered above.

---

## Design note: the Sober and Fitness filters

Both are wanted, neither is built — tracked as 4.1 and 4.2 in [BACKLOG.md](BACKLOG.md).
The reasoning is recorded here because it is a modelling decision, not a task.

Wanted, not yet built. They look like one task and are actually two, because they are
different *kinds* of thing — and getting that wrong is the main risk here.

**Fitness is a vibe.** It answers "what kind of event is this", the same question every
existing vibe answers, and it fills a real hole: an indoor yoga class or a gym event fits
none of the current nine (`outdoors` only works if it happens to be outside, and `local`
is a stretch). Adding it is additive and cheap:

- `Vibe.FITNESS` in `backend/app/enums.py`
- the matching entry in `admin/src/constants.js` and `frontend/src/constants.js`
- a `--vibe-fitness-1/-2` colour pair in `frontend/src/styles/tokens.css`, or generated
  posters for it fall back to grey
- **no migration** — `Event.vibe` is a `String(32)`, not a database enum

Known wrinkle: an outdoor run club is both `outdoors` and `fitness`, and an event carries
exactly one vibe. That is an existing limitation of the single-vibe model rather than
something Fitness introduces, but Fitness will make it visible more often.

**Sober is not a vibe, and must not be added as one.** It is an attribute that cuts
*across* categories: a sober rave is `nightlife` **and** alcohol-free; a dry comedy night
is `shows` **and** alcohol-free. Appending `SOBER` to the `Vibe` enum would force an
event to be either `nightlife` or `sober`, which makes a sober club night — precisely
what someone using this filter is looking for — impossible to express. It wants its own
column and its own control:

- `Event.alcohol_free: bool` defaulting to `False`, **which needs the first real Alembic
  migration** after the baseline
- an independent query param (`alcohol_free=true`), not another value in the `vibe` list
- a toggle in the filter sheet, sitting apart from the vibe chips, since it composes with
  them rather than replacing one
- a checkbox on the admin form

**Extraction honesty matters here.** A page not mentioning alcohol is not evidence the
event is alcohol-free. The system prompt should set `alcohol_free` only on an explicit
signal ("dry", "sober", "alcohol-free", "no bar") and otherwise leave it false, listing
it in `uncertain_fields` when it is genuinely ambiguous. Guessing wrong in the optimistic
direction sends someone in recovery to a bar, which is the one failure mode here that
actually hurts somebody.

Worth doing properly rather than bolting on: sober-curious and recovery audiences are
badly served in a city built on alcohol, and it is the kind of filter no competing Vegas
listing site offers.
