"""Shared rate limiter.

Lives in its own module so routers can import it without a circular dependency on
`main`. Client IPs are used transiently as the bucket key and held only in memory for
the length of the window — they are never written to the database or logged.
"""

from __future__ import annotations

from slowapi import Limiter

from .client_ip import client_ip

# Keyed on the resolved client rather than the socket peer. Behind Cloudflare and
# Railway the peer is always a proxy address, so `get_remote_address` — slowapi's
# default, and what this used before — gave every visitor in the world the same key and
# made the limits global rather than per-visitor. See client_ip.py.
limiter = Limiter(key_func=client_ip)
