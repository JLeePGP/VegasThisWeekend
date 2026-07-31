# Operations

Everything here needs dashboard access, so none of it can be done from code. Each section
says what to click, and — more usefully — how to tell afterwards whether it actually
worked, because most of these fail silently.

Do them in the order listed. Later steps assume earlier ones.

---

## 1. Cloudflare R2 — host our own media

**Why.** Two reasons, and the second is the important one.

A card that points at a venue's CDN goes blank the week they redesign their site. That's
the durability argument, and it's real.

The privacy argument is bigger. Every third-party image or video URL left on a card is a
request the visitor's browser makes to a host we don't control — which hands that host
the visitor's IP address, their user agent, and the page they were looking at. That is
enough to know someone in a particular city looked at a particular event. This app sets
no cookies and stores nothing that identifies anybody, and a single off-origin image
undoes a good part of that. Mirroring means the browser talks to our bucket and nobody
else.

The code is written and shipped. It's inert until these five environment variables exist.

**Steps.**

1. Cloudflare dashboard → **R2** → **Create bucket**. Name it `vtw-media`. Location:
   Automatic.
2. Bucket → **Settings** → **Public access** → **Connect a domain**. Use
   `media.vegasthisweekend.com`. Cloudflare creates the DNS record for you.
   - Use a custom domain, not the `r2.dev` development URL. `r2.dev` is rate-limited and
     not meant for production, and it puts a Cloudflare-branded hostname in front of
     visitors for no benefit.
3. R2 → **Manage R2 API Tokens** → **Create API Token**.
   - Permissions: **Object Read & Write**
   - Scope it to the `vtw-media` bucket only, not "all buckets".
   - Copy the Access Key ID and Secret Access Key **now** — the secret is shown once.
4. Save both into `Desktop\Vibe_Coding_Projects\Keys\VTW-r2-credentials.txt`, alongside
   the admin tokens. Not into the repo.
5. Railway → the API service → **Variables**, add:

   | Variable | Value |
   |---|---|
   | `R2_ACCOUNT_ID` | Cloudflare account ID (R2 overview page, right-hand side) |
   | `R2_ACCESS_KEY_ID` | from step 3 |
   | `R2_SECRET_ACCESS_KEY` | from step 3 |
   | `R2_BUCKET` | `vtw-media` |
   | `R2_PUBLIC_BASE_URL` | `https://media.vegasthisweekend.com` |

   All five must be set. The app treats any one of them being blank as "R2 is not
   configured" and keeps the original URLs — it does not half-enable.

**How to tell it worked.** Save an event in the admin panel with an image URL. The saved
event's `image_url` should now start with `https://media.vegasthisweekend.com/events/`.
If it still points at the original host, the panel shows a warning saying why — read it.
Video mirrors the same way, into `/video/` instead of `/events/`.

**Then tighten the CSP.** Once media is mirroring, edit
[frontend/public/\_headers](frontend/public/_headers) and narrow these two:

```
img-src 'self' data: https://media.vegasthisweekend.com;
media-src 'self' https://media.vegasthisweekend.com;
```

They currently allow any `https:` host, which is what makes an unmirrored URL work at
all. After tightening, an unmirrored image silently fails to load and falls back to the
generated poster — which is the correct behaviour, but do it only after confirming
mirroring works, or every card goes blank at once.

**Cost.** R2 charges for storage and operations but **not for egress**, which is the
usual bill-killer. At this scale — a few hundred images and a handful of short videos —
expect the free tier (10 GB storage, 1M writes/month, 10M reads/month) to cover it
entirely.

---

## 2. Turn off Cloudflare Web Analytics

**Why.** The beacon is injected at the Cloudflare edge, so it never appears in this
repo's HTML — an "it isn't in the source" check will not find it. It loads a script from
`static.cloudflareinsights.com` into every visitor's browser and reports back to
Cloudflare.

The app already has its own server-side counters, which see nothing beyond what the HTTP
request already told us and store no identifiers at all. So the beacon is a third-party
script collecting visitor data to tell us something we already know.

**Steps.**

1. Cloudflare → the `vegasthisweekend.com` zone → **Analytics & Logs** → **Web
   Analytics** → toggle the site **off**.

The CSP entries that allowed it have already been removed from `_headers`. Those two
changes go together and neither alone is enough:

- CSP removed but the toggle still on → the beacon is still injected, and every visitor's
  browser prints a console violation instead of quietly not being tracked.
- Toggle off but CSP entries left in → nothing breaks, but the policy still advertises a
  third-party host we don't use.

**Current state, measured 30 Jul 2026.** The deployed CSP is now `script-src 'self'` with
nothing else, and the served HTML contains exactly one script tag — the app bundle. So
the beacon is not being injected right now. Treat the dashboard step as confirming that
rather than changing it, and check the toggle anyway: whether it is on is not something
the page can tell you reliably, and it can be turned on later by accident.

**How to tell it worked.** Load https://vegasthisweekend.com with DevTools open. The
Network tab should show no request to any `cloudflareinsights.com` host, and the Console
should show no CSP violation. Cloudflare's own traffic analytics (the zone-level one) is
unaffected and stays available — that's server-side and doesn't touch the visitor.

---

## 3. Cache the API at the edge

**Why.** The event listing is identical for every visitor. Without this, a thousand
people opening the site is a thousand round trips to Postgres for the same rows. With it,
it's roughly one per distinct filter combination per minute.

The API already sends `Cache-Control: public, max-age=0, s-maxage=60,
stale-while-revalidate=120` on `/events` and `/events/{id}` and nothing else. Cloudflare
ignores `Cache-Control` on proxied requests unless you tell it not to.

**Steps.**

1. Cloudflare → the zone → **Caching** → **Cache Rules** → **Create rule**.
2. Name: `Cache API listings`.
3. When incoming requests match:
   - Hostname equals `api.vegasthisweekend.com`
   - **and** URI Path starts with `/events`
4. Then:
   - Cache eligibility: **Eligible for cache**
   - Edge TTL: **Use cache-control header if present, use default otherwise** (default 60s)
   - Browser TTL: **Respect origin TTL**
5. Deploy.

**Scope this rule carefully.** It must match `/events` and nothing else. `/share/{token}`
is one person's saved list and `/admin/*` is behind a bearer token; caching either would
mean the edge serving one person's response to somebody else. The path condition is the
only thing preventing that, so don't loosen it to `/`.

**How to tell it worked.**

```bash
curl -s -D - -o /dev/null "https://api.vegasthisweekend.com/events?date=all" | grep -i cf-cache-status
```

First request says `MISS`, the second within a minute says `HIT`. Before the rule exists
it says `DYNAMIC`, which is how you know the rule is the missing piece rather than the
headers.

Use `-D - -o /dev/null` rather than `curl -I`. `-I` sends a HEAD request and FastAPI
answers those with 405, so you get a status line that tells you nothing about caching.

Then check the negative case — this is the one that actually matters:

```bash
curl -s -D - -o /dev/null https://api.vegasthisweekend.com/admin/events | grep -i cf-cache-status
```

It must never say `HIT`.

**Already verified from the origin side** (30 Jul 2026, against production): `/events`
and `/events/{id}` send the caching header; `/share/{token}`, `/admin/events` and
`/health` send no `Cache-Control` at all. So the only thing standing between here and a
working edge cache is the rule itself.

---

## 4. Lock the origin to Cloudflare

**Why.** Rate limiting trusts `CF-Connecting-IP` to work out whose bucket a request
belongs to. That header is trivially forgeable by anyone who skips Cloudflare and hits
`vegasthisweekend-production.up.railway.app` directly — which is still publicly
reachable, because Railway assigns that hostname and there's no way to remove it.

The consequence isn't an auth bypass (nothing here decides who you are), but someone can
claim another visitor's IP and exhaust *their* rate limit — a denial of service against
one person at a time. A shared secret that only Cloudflare knows closes it.

**This is deliberately a two-stage rollout.** Doing it in one step takes the API down if
anything is slightly off.

### Stage 1 — set the secret (safe; rejects nothing)

1. Generate a long random value. In PowerShell:
   `-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | % {[char]$_})`
2. Save it to `Desktop\Vibe_Coding_Projects\Keys\VTW-proxy-secret.txt`.
3. Railway → Variables → `PROXY_SHARED_SECRET` = that value. Leave
   `REQUIRE_PROXY_SECRET` unset.
4. Cloudflare → the zone → **Rules** → **Transform Rules** → **Modify Request Header** →
   **Create rule**.
   - Name: `Origin shared secret`
   - When: Hostname equals `api.vegasthisweekend.com`
   - Then: **Set static** → header name `x-vtw-proxy-secret`, value = the same secret
   - Deploy.

At this point nothing is rejected. A request carrying the secret gets its
`CF-Connecting-IP` believed; one without it is rate-limited on its socket address
instead. If the Transform Rule is wrong, the only symptom is the rate-limit bucketing we
already had.

### Stage 2 — enforce it

**Before enabling, confirm both of these**, using the admin panel's diagnostics
(`/admin/diagnostics/client`, reachable with the admin token):

- Called through `api.vegasthisweekend.com` → `proxy_secret.secret_matches` is **true**
- Called against the raw `*.up.railway.app` hostname → **false**

If both hold, set `REQUIRE_PROXY_SECRET=true` in Railway. Anything without the secret now
gets a 403.

The diagnostics response looks like this (measured against production, 30 Jul 2026,
before the secret was set):

```json
"proxy_secret": {
  "secret_configured": false,
  "secret_present_on_this_request": false,
  "secret_matches": false,
  "requirement_enforced": false
}
```

After stage 1, `secret_configured` and `secret_matches` should both read true through the
custom domain.

**Two things that will bite.**

- `/health` is exempt, deliberately. Railway's healthcheck hits the container directly,
  never through Cloudflare — without the exemption every deploy would fail its
  healthcheck and roll back while the logs showed a perfectly healthy app.
- The admin panel used to point at the raw Railway hostname, which enforcement would have
  403'd. `admin/.env` now points at `https://api.vegasthisweekend.com`. If you ever point
  it back for testing, enforcement will lock the panel out.

**Rollback.** Delete `REQUIRE_PROXY_SECRET` (or set it false) in Railway. Takes effect on
the next boot.

---

## 5. Database backups

**Why.** There are real events in production now, entered by hand. Losing them is losing
work that can't be regenerated, and this app has already survived one accidental
`downgrade` that wiped a dev database.

### Confirm snapshots exist

1. Railway → the **Postgres** service → **Backups**.
2. Confirm scheduled backups are on and note the retention window.
3. If they're off, turn them on. Daily is right for this.

### Verify a backup actually restores

An untested backup is a guess. Nothing about a snapshot existing says it holds the rows
you think it does.

```bash
cd backend
python scripts/verify_backup.py --database-url "<the Railway DATABASE_URL>"
```

It dumps production (read-only), restores into a scratch database, compares row counts
per table, and drops the scratch database afterwards. Needs `pg_dump` and `psql` on PATH
at a major version matching the server.

A small drift on `stat_counters` between the count and the dump is normal if the site was
being used mid-run — that table moves constantly. Any difference on `events` or
`share_lists` is not drift; re-run and investigate.

Run it before any migration, and once a month otherwise.

### Also restore one by hand, once

The script proves a dump you take now round-trips. It does **not** prove Railway's
scheduled snapshots are being taken, retained, or are restorable — only actually
restoring one shows that. Do it once, early, while nothing depends on the answer.

---

## Quick reference — what proves what

| Change | The check that isn't self-deceiving |
|---|---|
| R2 configured | A saved event's `image_url` starts with `media.vegasthisweekend.com` |
| CSP tightened | Cards still render after narrowing `img-src`/`media-src` |
| Beacon off | No `cloudflareinsights.com` request in the Network tab, no console violation |
| Edge cache on | `cf-cache-status: HIT` on `/events`, and **never** on `/admin/events` |
| Proxy secret | `secret_matches` true via the custom domain, false via the raw Railway host |
| Backups | `verify_backup.py` passes, **and** one snapshot restored by hand at least once |
