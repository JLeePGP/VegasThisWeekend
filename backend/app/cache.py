"""A tiny in-process cache for values that are read on every request and change rarely.

Two things were being recomputed on every call to the events list: whether any sample
data remains (a COUNT over the whole table, purely to decide if a banner shows) and the
full set of insider tips. Neither changes between one visitor and the next, and both were
costing a database round trip per request — four in total for a single list call.

Deliberately in-process rather than Redis. The values are small, identical for every
visitor, and cheap to recompute, so the worst case of a cold instance is one extra query.
Reaching for shared storage here would add a dependency to solve a problem that a
dictionary solves.

The trade is staleness across instances: after an admin edit, an instance can serve the
old value until its entry expires. TTLs are short and the affected values are a banner
and a tip line — nothing where being seconds behind matters. `invalidate()` exists so the
admin write paths can clear it immediately on the instance that handled the write.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

# Short enough that an admin edit shows up while you are still looking at the screen.
DEFAULT_TTL_SECONDS = 30.0

_lock = threading.Lock()
_entries: dict[str, tuple[float, Any]] = {}


def get_or_set(key: str, producer: Callable[[], Any], ttl: float = DEFAULT_TTL_SECONDS) -> Any:
    """Return the cached value, or produce and store it.

    The producer runs outside the lock. Two requests racing on a cold key will both
    compute it, which is one wasted query rather than a held lock across a database
    round trip — the wrong thing to serialise every request behind.
    """
    now = time.monotonic()
    with _lock:
        entry = _entries.get(key)
        if entry is not None and entry[0] > now:
            return entry[1]

    value = producer()

    with _lock:
        _entries[key] = (time.monotonic() + ttl, value)
    return value


def invalidate(*keys: str) -> None:
    """Drop cached entries. No argument clears everything."""
    with _lock:
        if not keys:
            _entries.clear()
            return
        for key in keys:
            _entries.pop(key, None)


# Keys are named here rather than spelled inline at each call site, so a typo is an
# ImportError rather than a cache that silently never hits.
SAMPLE_DATA = "events:sample_data"
TIP_BUCKETS = "tips:buckets"
