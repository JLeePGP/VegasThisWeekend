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

    Takes a Counter keyed by (metric, event_id) and writes the whole batch in at most two
    statements. Returns the number of counters touched.

    Two rather than one because a per-event counter and a site-wide counter resolve their
    conflicts against two different partial unique indexes — see StatCounter — and a
    single INSERT can only name one. So the rows are split by that and each group goes in
    as one multi-row upsert.

    This matters at load: a visitor working through a stack sends a batch every few
    seconds, and the old shape put a round trip on the wire for every distinct
    (metric, event) pair in it. Twenty swipes across ten events was twenty statements
    inside one transaction; it is now two.
    """
    if not counts:
        return 0

    day = vegas_today()

    per_event: list[dict] = []
    site_wide: list[dict] = []
    for (metric, event_id), amount in counts.items():
        if amount <= 0:
            continue
        row = {"day": day, "metric": metric.value, "event_id": event_id, "count": amount}
        (per_event if event_id else site_wide).append(row)

    if not per_event and not site_wide:
        return 0

    insert = _insert_for(session)

    groups = (
        (per_event, ["day", "metric", "event_id"], StatCounter.event_id.is_not(None)),
        (site_wide, ["day", "metric"], StatCounter.event_id.is_(None)),
    )
    for rows, index_elements, index_where in groups:
        if not rows:
            continue
        statement = insert(StatCounter).values(rows)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=index_elements,
                index_where=index_where,
                # `excluded` is the row this statement proposed, so each row in the batch
                # adds its own amount. A literal would apply one row's amount to all of
                # them — the reason this cannot simply be `count + amount` any more.
                #
                # Safe against a row conflicting with itself only because the input is a
                # Counter: every (metric, event_id) appears once, and Postgres rejects a
                # statement that tries to update the same row twice.
                set_={"count": StatCounter.count + statement.excluded.count},
            )
        )

    session.commit()
    return len(per_event) + len(site_wide)


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
        skips = entry["metrics"].get("skip", 0)
        # A save *rate* needed a denominator, and the swipe deck supplied one: a swipe
        # left was an explicit no. A list has no such thing — scrolling past a row is not
        # a decision, and there is no impression counter to stand in for one.
        #
        # So the rate is reported only where skips exist, which now means only the data
        # recorded before 1 Aug 2026. The alternative was saves/(saves+0), which is 100%
        # for every event that has ever been saved and 0% for the rest: a number that
        # looks like a measurement and is not one. Events rank by saves instead.
        entry["decisions"] = saves + skips
        entry["save_rate"] = round(saves / (saves + skips), 3) if skips else None

    by_vibe: dict[str, dict[str, int]] = {}
    for entry in events.values():
        bucket = by_vibe.setdefault(entry["vibe"], {"saves": 0, "skips": 0})
        bucket["saves"] += entry["metrics"].get(Metric.SAVE.value, 0)
        bucket["skips"] += entry["metrics"].get("skip", 0)
    for bucket in by_vibe.values():
        # Same reasoning as above: no skips means no denominator, not a perfect score.
        skips = bucket["skips"]
        bucket["save_rate"] = round(bucket["saves"] / (bucket["saves"] + skips), 3) if skips else None

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
