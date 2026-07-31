"""Working out who a request actually came from.

This exists because rate limiting was keyed on the socket peer, and in production that
peer is never the visitor. Two proxies sit in front of this app — Cloudflare, then
Railway — so every request arrives from a Railway address. Every visitor therefore
shared a single rate-limit bucket, and the 100/minute limit on the public endpoints was
100/minute *in total*: enough real traffic and genuine users start getting 429s while the
logs show nothing wrong.

Uvicorn will read `X-Forwarded-For` itself, but only from peers it trusts, and
`forwarded_allow_ips` defaults to 127.0.0.1. Railway's proxy is not localhost, so that
never applied here.

Measured against the deployed API, one request from a browser:

    cf_connecting_ip       2600:880a:2800:4100:...      <- the actual visitor
    x_forwarded_for_raw    104.23.203.139, 79.127.217.65
    socket_peer            100.64.0.2

Two things worth keeping. `100.64.0.2` is RFC 6598 shared address space — Railway's
internal proxy — and it is what every visitor on earth was being keyed on.

And the ordering below is not a preference, it is load-bearing: the left-most
`X-Forwarded-For` entry here is `104.23.203.139`, which is a *Cloudflare edge* address,
not the visitor. Falling back to X-Forwarded-For first would have swapped one shared
bucket for a slightly larger set of shared buckets — everyone routed through the same
Cloudflare PoP together — and looked like it worked.

SECURITY — what trusting a header does and does not cost.

These headers are only meaningful if the request genuinely came through Cloudflare. The
raw `*.up.railway.app` hostname is still publicly reachable, so someone who goes straight
there can put whatever they like in `CF-Connecting-IP`. Two consequences, both bounded:

  * They can evade their own rate limit — but so could anyone with a handful of IPs, and
    these are public read endpoints.
  * They can poison another visitor's bucket by claiming that visitor's address, which
    is a denial of service against one person at a time.

Neither is an authentication bypass; nothing here decides who you are. Weighed against
the certainty that everybody currently shares one bucket, trusting the header is the
better failure mode — but it is a trade, not a fix, and `TRUST_PROXY_HEADERS` exists so
it can be turned off.

This is now closed, when configured: proxy_guard.py checks a secret that only Cloudflare
knows, and a request that does not carry it has its forwarding headers ignored and is
keyed on its socket peer instead. Until `PROXY_SHARED_SECRET` is set and the matching
Cloudflare Transform Rule exists, the trade above is still what is in force.
"""

from __future__ import annotations

from fastapi import Request
from slowapi.util import get_remote_address

from .config import get_settings
from .proxy_guard import came_through_proxy


def resolve(request: Request) -> dict[str, str | None]:
    """What each candidate source says. Returned as a dict so the diagnostics endpoint
    and the key function agree by construction rather than by being written twice."""
    headers = request.headers
    forwarded = headers.get("x-forwarded-for")
    return {
        "cf_connecting_ip": headers.get("cf-connecting-ip"),
        # Left-most entry is the original client; everything after it is a proxy hop.
        "x_forwarded_for_first": forwarded.split(",")[0].strip() if forwarded else None,
        "x_forwarded_for_raw": forwarded,
        "socket_peer": get_remote_address(request),
        # Present on anything that really came via Cloudflare. Not proof — it is as
        # forgeable as the rest — but its absence on a request claiming to be from
        # Cloudflare is a useful smell.
        "cf_ray": headers.get("cf-ray"),
    }


def client_ip(request: Request) -> str:
    """The rate-limit bucket key."""
    if not get_settings().trust_proxy_headers:
        return get_remote_address(request) or "unknown"

    # A request that did not come through Cloudflare has forwarding headers that mean
    # nothing — anyone hitting the raw Railway hostname sets them to whatever they like.
    # Keying on the socket peer instead means such a request can only affect its own
    # bucket, not somebody else's.
    if not came_through_proxy(request):
        return get_remote_address(request) or "unknown"

    sources = resolve(request)
    # Cloudflare's own header first, and the order matters — see the measurement in the
    # module docstring, where X-Forwarded-For's first entry was a Cloudflare edge
    # address rather than the visitor. It is also a single value Cloudflare overwrites,
    # rather than a list a client can prepend to.
    return (
        sources["cf_connecting_ip"]
        or sources["x_forwarded_for_first"]
        or sources["socket_peer"]
        or "unknown"
    )
