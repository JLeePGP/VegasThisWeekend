"""Telling a request that came through Cloudflare from one that did not.

This closes the hole documented at length in client_ip.py. Rate limiting trusts
`CF-Connecting-IP` to decide whose bucket a request belongs to, and that header is
trivially forgeable by anyone who bypasses Cloudflare and hits the raw
`*.up.railway.app` hostname directly — which is still publicly reachable, because
Railway assigns it and there is no way to un-assign it.

The fix is a shared secret that only Cloudflare knows: a Transform Rule adds a header at
the edge, and this module checks it. A request without the secret did not come through
Cloudflare, so its forwarding headers mean nothing and are ignored.

WHY THIS IS TWO SETTINGS RATHER THAN ONE
----------------------------------------
`PROXY_SHARED_SECRET` alone changes only what is *believed*: a request carrying the
secret gets its `CF-Connecting-IP` trusted, one without it is keyed on the socket peer
instead. Nothing is rejected, so it is safe to deploy before the Cloudflare rule exists —
the failure mode is the behaviour we already had.

`REQUIRE_PROXY_SECRET` is the second stage and does reject. Turning it on before the
Transform Rule is live and confirmed takes the whole API down, which is why it is a
separate switch and defaults off. The order is: set the secret, deploy, add the rule,
confirm `/admin/diagnostics/client` reports the secret arriving, then turn on the
requirement.

WHAT IT DOES NOT DO
-------------------
This is not authentication — admin routes are protected by their own bearer token and do
not depend on any of this. It also cannot hide the origin from someone who has the
secret, and the secret travels in a plain header, so it is only as private as the TLS
connection carrying it. What it buys is that an attacker cannot claim to be a particular
visitor, which is the one consequence in client_ip.py that harms somebody other than
themselves.
"""

from __future__ import annotations

import hmac

from fastapi import Request

from .config import get_settings

# Chosen to be obviously ours and not to collide with anything Cloudflare or Railway
# sets. Cloudflare adds it as a Transform Rule → Modify Request Header → Set static.
PROXY_SECRET_HEADER = "x-vtw-proxy-secret"


def came_through_proxy(request: Request) -> bool:
    """Whether this request carries the shared secret.

    Returns True when no secret is configured: with nothing to check against, the old
    behaviour (believe the forwarding headers) is what the deployment expects, and
    silently distrusting every header would reintroduce the single shared rate-limit
    bucket without saying so.
    """
    secret = get_settings().proxy_shared_secret
    if not secret:
        return True

    presented = request.headers.get(PROXY_SECRET_HEADER)
    if not presented:
        return False
    # compare_digest rather than ==: a plain comparison returns as soon as two bytes
    # differ, and the time it takes leaks how much of the secret was correct.
    return hmac.compare_digest(presented, secret)


def secret_status(request: Request) -> dict[str, bool]:
    """What the diagnostics endpoint reports, so the Cloudflare rule can be verified
    from the admin panel rather than guessed at."""
    settings = get_settings()
    return {
        "secret_configured": bool(settings.proxy_shared_secret),
        "secret_present_on_this_request": bool(request.headers.get(PROXY_SECRET_HEADER)),
        "secret_matches": came_through_proxy(request)
        and bool(settings.proxy_shared_secret),
        "requirement_enforced": settings.require_proxy_secret,
    }
