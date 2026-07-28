"""Shared rate limiter.

Lives in its own module so routers can import it without a circular dependency on
`main`. Client IPs are used transiently as the bucket key and held only in memory for
the length of the window — they are never written to the database or logged.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
