"""Prove a Postgres backup can actually be restored.

An untested backup is a guess. Railway takes snapshots, but nothing about a snapshot
existing says it contains the rows you think it does or that it restores into a working
schema — and the moment you find out is always the moment you needed it.

What this does: takes a dump, restores it into a scratch database, and then checks the
restored copy against what production actually holds. It never touches production beyond
reading, and it drops the scratch database at the end.

    python scripts/verify_backup.py --database-url "$PROD_URL"

Add --keep to leave the restored database in place for poking at.

Requires `pg_dump` and `psql` on PATH, matching the server's major version. On Windows
they ship with the Postgres installer, usually in
C:\\Program Files\\PostgreSQL\\<version>\\bin — add that to PATH if the script cannot
find them.

WHAT THIS DOES NOT PROVE
------------------------
It proves *a* dump taken right now restores cleanly. It does not prove Railway's own
scheduled snapshots are being taken, retained, or are restorable — only the Railway
dashboard shows that, and restoring one is a manual step. Treat this as the check that
the data and schema survive a round trip; treat the dashboard as the check that
snapshots exist. Both matter and neither substitutes for the other.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# Tables whose row counts must survive the round trip. Deliberately explicit rather than
# "every table in the schema": a table added and then forgotten should show up as a
# failure to update this list, not silently go unverified.
VERIFIED_TABLES = [
    "events",
    "event_tags",
    "insider_tips",
    "share_lists",
    "stat_counters",
    "extraction_drafts",
]


class VerificationFailed(RuntimeError):
    pass


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    if result.returncode != 0:
        raise VerificationFailed(
            f"{command[0]} failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    return result.stdout


def require_tools() -> None:
    missing = [tool for tool in ("pg_dump", "psql") if shutil.which(tool) is None]
    if missing:
        raise VerificationFailed(
            f"Not on PATH: {', '.join(missing)}. Install the Postgres client tools and "
            "make sure their major version matches the server."
        )


def normalise(url: str) -> str:
    """Strip the SQLAlchemy driver suffix psql does not understand."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgres://", "postgresql://", 1
    )


def with_database(url: str, name: str) -> str:
    parsed = urlparse(normalise(url))
    return urlunparse(parsed._replace(path=f"/{name}"))


def count_rows(url: str, table: str) -> int:
    """Returns -1 when the table does not exist, which is itself a finding."""
    output = run(
        [
            "psql",
            normalise(url),
            "-tA",
            "-c",
            f"SELECT count(*) FROM {table};",
        ]
    ).strip()
    return int(output) if output else 0


def table_exists(url: str, table: str) -> bool:
    output = run(
        [
            "psql",
            normalise(url),
            "-tA",
            "-c",
            "SELECT to_regclass('public." + table + "') IS NOT NULL;",
        ]
    ).strip()
    return output == "t"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Production connection string. Defaults to $DATABASE_URL.",
    )
    parser.add_argument(
        "--scratch-name",
        default=f"vtw_restore_check_{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
        help="Name of the temporary database to restore into.",
    )
    parser.add_argument("--keep", action="store_true", help="Do not drop the scratch database.")
    args = parser.parse_args()

    if not args.database_url:
        print("No database URL. Pass --database-url or set DATABASE_URL.", file=sys.stderr)
        return 2

    require_tools()

    source = normalise(args.database_url)
    admin_url = with_database(source, "postgres")
    scratch_url = with_database(source, args.scratch_name)

    print("Reading production row counts...")
    expected: dict[str, int] = {}
    for table in VERIFIED_TABLES:
        if not table_exists(source, table):
            raise VerificationFailed(
                f"Table {table!r} does not exist in the source database. Either the "
                "schema has moved on and VERIFIED_TABLES is stale, or this URL points "
                "somewhere unexpected — check before going further."
            )
        expected[table] = count_rows(source, table)
        print(f"  {table:<20} {expected[table]:>8}")

    with tempfile.TemporaryDirectory() as tmp:
        dump_path = Path(tmp) / "backup.dump"

        print("\nTaking a dump...")
        run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "-f", str(dump_path), source])
        size_mb = dump_path.stat().st_size / 1_000_000
        print(f"  {size_mb:.2f} MB")
        if dump_path.stat().st_size == 0:
            raise VerificationFailed("pg_dump produced an empty file.")

        print(f"\nRestoring into {args.scratch_name}...")
        run(["psql", admin_url, "-c", f'CREATE DATABASE "{args.scratch_name}";'])
        try:
            # pg_restore exits non-zero on benign notices (an extension already present,
            # a role that does not exist here), so failures are judged by the row counts
            # below rather than by its exit status.
            subprocess.run(
                ["pg_restore", "--no-owner", "--no-acl", "-d", scratch_url, str(dump_path)],
                capture_output=True,
                text=True,
            )

            print("\nComparing the restored copy against production...")
            mismatches = []
            for table, want in expected.items():
                if not table_exists(scratch_url, table):
                    mismatches.append(f"  {table}: missing from the restored database")
                    continue
                got = count_rows(scratch_url, table)
                marker = "ok" if got == want else "MISMATCH"
                print(f"  {table:<20} {want:>8} -> {got:>8}  {marker}")
                if got != want:
                    mismatches.append(f"  {table}: expected {want}, restored {got}")

            if mismatches:
                raise VerificationFailed(
                    "The restored database does not match production:\n"
                    + "\n".join(mismatches)
                    + "\n\nA count can legitimately differ if the site was written to "
                    "mid-dump — stat_counters moves constantly. Re-run before treating "
                    "a small drift on that table as a real failure; any difference in "
                    "events or share_lists is not drift."
                )
        finally:
            if args.keep:
                print(f"\nLeft {args.scratch_name} in place (--keep).")
            else:
                print(f"\nDropping {args.scratch_name}...")
                run(["psql", admin_url, "-c", f'DROP DATABASE IF EXISTS "{args.scratch_name}";'])

    print("\nBackup verified: a dump taken now restores with matching row counts.")
    print("This says nothing about Railway's scheduled snapshots — check those in the")
    print("dashboard, and restore one by hand at least once.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except VerificationFailed as error:
        print(f"\nFAILED: {error}", file=sys.stderr)
        sys.exit(1)
