"""Recording and reading interaction counters.

Kept out of the routers because the upsert has to be portable: the same statement runs
against SQLite locally and Postgres in production, and the two spell "insert or add to
the existing row" differently enough that guessing is a bug waiting to happen.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .enums import Metric
from .models import Event, StatCounter
from .timewindow import VEGAS_TZ


def vegas_today() -> date:
    """The calendar day in Las Vegas. See the note on StatCounter for why this is not
    the 5am listing day."""
    return datetime.now(VEGAS_TZ).date()


def _insert_for(session: Session):
    """The dialect's INSERT, so `on_conflict_do_update` is available.

    SQLAlchemy's generic insert() has no upsert; both dialects support one, with the
    same API but from different modules.
    """
    name = session.get_bind().dialect.name
    if name == "postgresql":
        return pg_insert
    if name == "sqlite":
        return sqlite_insert
    raise RuntimeError(f"No upsert support wired up for dialect {name!r}.")


def record(session: Session, counts: Counter[tuple[Metric, str | None]]) -> int:
    """Add a batch of interactions to today's counters.

    Takes a Counter keyed by (metric, event_id) so a burst of twenty swipes becomes a
    handful of statements rather than twenty. Returns the number of counters touched.
    """
    if not counts:
        return 0

    insert = _insert_for(session)
    day = vegas_today()

    for (metric, event_id), amount in counts.items():
        if amount <= 0:
            continue

        statement = insert(StatCounter).values(
            day=day,
            metric=metric.value,
            event_id=event_id,
            count=amount,
        )
        # The index the conflict resolves against depends on whether this is a per-event
        # or a site-wide counter, because they are enforced by two different partial
        # unique indexes — see StatCounter.
        index_elements = ["day", "metric", "event_id"] if event_id else ["day", "metric"]
        index_where = (
            StatCounter.event_id.is_not(None) if event_id else StatCounter.event_id.is_(None)
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=index_elements,
                index_where=index_where,
                # Add to whatever is already there rather than overwriting it.
                set_={"count": StatCounter.count + amount},
            )
        )

    session.commit()
    return len(counts)


def summary(session: Session, days: int = 30) -> dict:
    """Everything the admin dashboard shows, in one pass."""
    since = vegas_today() - timedelta(days=days - 1)

    totals_rows = session.execute(
        select(StatCounter.metric, func.sum(StatCounter.count))
        .where(StatCounter.day >= since)
        .group_by(StatCounter.metric)
    ).all()
    totals = {metric: int(total or 0) for metric, total in totals_rows}

    daily_rows = session.execute(
        select(StatCounter.day, StatCounter.metric, func.sum(StatCounter.count))
        .where(StatCounter.day >= since)
        .group_by(StatCounter.day, StatCounter.metric)
        .order_by(StatCounter.day.asc())
    ).all()
    daily: dict[str, dict[str, int]] = {}
    for day, metric, total in daily_rows:
        daily.setdefault(day.isoformat(), {})[metric] = int(total or 0)

    # Per-event totals, joined back to the event so the dashboard can name them.
    per_event_rows = session.execute(
        select(
            Event.id,
            Event.name,
            Event.vibe,
            Event.start_at,
            StatCounter.metric,
            func.sum(StatCounter.count),
        )
        .join(StatCounter, StatCounter.event_id == Event.id)
        .where(StatCounter.day >= since)
        .group_by(Event.id, Event.name, Event.vibe, Event.start_at, StatCounter.metric)
    ).all()

    events: dict[str, dict] = {}
    for event_id, name, vibe, start_at, metric, total in per_event_rows:
        entry = events.setdefault(
            event_id,
            {"id": event_id, "name": name, "vibe": vibe, "start_at": start_at, "metrics": {}},
        )
        entry["metrics"][metric] = int(total or 0)

    for entry in events.values():
        saves = entry["metrics"].get(Metric.SAVE.value, 0)
        skips = entry["metrics"].get(Metric.SKIP.value, 0)
        decisions = saves + skips
        # The number that actually ranks an event: of the people who saw it and decided,
        # how many wanted it. Raw saves just rank by how long a card sat near the top of
        # the stack.
        entry["save_rate"] = round(saves / decisions, 3) if decisions else None
        entry["decisions"] = decisions

    by_vibe: dict[str, dict[str, int]] = {}
    for entry in events.values():
        bucket = by_vibe.setdefault(entry["vibe"], {"saves": 0, "skips": 0})
        bucket["saves"] += entry["metrics"].get(Metric.SAVE.value, 0)
        bucket["skips"] += entry["metrics"].get(Metric.SKIP.value, 0)
    for bucket in by_vibe.values():
        decisions = bucket["saves"] + bucket["skips"]
        bucket["save_rate"] = round(bucket["saves"] / decisions, 3) if decisions else None

    return {
        "days": days,
        "since": since.isoformat(),
        "totals": totals,
        "daily": daily,
        "events": sorted(
            events.values(),
            key=lambda e: e["metrics"].get(Metric.SAVE.value, 0),
            reverse=True,
        ),
        "by_vibe": by_vibe,
    }
