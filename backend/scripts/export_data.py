"""Export every row in the database to a single JSON file.

This exists because Railway gates scheduled snapshots behind a paid plan, so the events
John has entered by hand had no backup at all. It needs nothing but `psycopg`, which the
API already depends on — no `pg_dump`, no Postgres client install, no subscription.

    python scripts/export_data.py --url-file "path/to/VTW-database-url.txt"
    python scripts/export_data.py --database-url "$DATABASE_URL"

WHAT THIS IS AND IS NOT
-----------------------
It is a *data* export: every row of every table, plus the alembic revision the schema was
at. That is enough to rebuild the catalog, which is the thing that cannot be regenerated —
the events were typed in by a person.

It is not a `pg_dump`. It does not capture indexes, constraints, sequences, or the schema
itself, so restoring means running migrations to the recorded revision first and then
loading the rows back. For a database this size that is a fine trade for not needing the
Postgres client tools at all; `verify_backup.py` remains the real round-trip check for
when those tools exist.

Tables are discovered from the catalog rather than listed, deliberately: a table added and
then forgotten silently goes unbacked-up otherwise, and the whole failure mode here is
finding out too late.

One consequence of that, worth knowing before handling an export: since `subscribers`
exists, a dump contains newsletter email addresses. It belongs in the private backup
bucket and nowhere else — not a Downloads folder that syncs, not an attachment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

# The URL may arrive with SQLAlchemy's driver suffix, or as the older `postgres://` scheme
# that psycopg no longer accepts.
_URL_PATTERN = re.compile(r"postgres(?:ql)?(?:\+\w+)?://\S+")


def normalise(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgres://", "postgresql://", 1
    )


def url_from_file(path: Path) -> str:
    """Pull a connection string out of a file that may hold notes around it.

    Read rather than passed on the command line so the secret never lands in a shell
    history, a process list, or this project's transcripts.
    """
    raw = path.read_text(encoding="utf-8-sig")
    found = _URL_PATTERN.search(raw)
    if not found:
        raise SystemExit(f"No postgres:// URL found in {path}")
    return normalise(found.group(0))


def encode(value):
    """JSON has no date, interval, decimal or bytes. Everything becomes a string.

    Decimal goes to str rather than float on purpose — float would silently round money
    and this is a backup, where a lossy conversion is the one thing you cannot notice
    until you need the data back.
    """
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"No JSON encoding for {type(value).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export all rows to JSON.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--url-file", type=Path, help="File containing the connection string.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path.home() / "Desktop" / "Vibe_Coding_Projects" / "VTW-backups",
        help="Where to write. Defaults outside the repo, so a dump is never committed.",
    )
    parser.add_argument(
        "--upload-r2",
        action="store_true",
        help="Also upload to the private backup bucket (see R2_BACKUP_* environment vars).",
    )
    args = parser.parse_args()

    if args.url_file:
        url = url_from_file(args.url_file)
    elif args.database_url:
        url = normalise(args.database_url)
    else:
        print("Need --url-file, --database-url, or $DATABASE_URL.", file=sys.stderr)
        return 2

    import psycopg

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = args.out_dir / f"vtw-backup-{stamp}.json"

    export: dict[str, object] = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "tables": {},
    }

    with psycopg.connect(url, connect_timeout=30) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            export["server_version"] = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                # Identifier quoted, not parameterised: table names cannot be bound as
                # values, and these come from the catalog rather than from user input.
                cursor.execute(f'SELECT * FROM "{table}"')
                columns = [description[0] for description in cursor.description]
                rows = [dict(zip(columns, record)) for record in cursor.fetchall()]
                export["tables"][table] = rows
                print(f"  {table:<24}{len(rows):>8}")

    destination.write_text(
        json.dumps(export, indent=2, default=encode, ensure_ascii=False), encoding="utf-8"
    )

    total = sum(len(rows) for rows in export["tables"].values())
    size_kb = destination.stat().st_size / 1000
    print(f"\n{total} rows across {len(export['tables'])} tables -> {destination}")
    print(f"{size_kb:.1f} KB")

    if args.upload_r2:
        key = upload_to_r2(destination)
        print(f"uploaded to r2://{os.environ['R2_BACKUP_BUCKET']}/{key}")

    return 0


def upload_to_r2(path: Path) -> str:
    """Copy a finished export into the private backup bucket.

    Deliberately separate credentials from the ones in `app/images.py`. That bucket is
    public — it is served at media.vegasthisweekend.com — and a database export placed in
    it would be readable by anyone who guessed the key. The media token is also scoped to
    the media bucket alone, so it cannot write here even by mistake. Two buckets, two
    tokens, and the public one can never hold a backup.
    """
    import boto3
    from botocore.config import Config as BotoConfig

    required = (
        "R2_ACCOUNT_ID",
        "R2_BACKUP_ACCESS_KEY_ID",
        "R2_BACKUP_SECRET_ACCESS_KEY",
        "R2_BACKUP_BUCKET",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"--upload-r2 needs these environment variables: {', '.join(missing)}")

    # Foldered by year-month so a listing stays readable after a few hundred nights.
    key = f"db/{datetime.now():%Y-%m}/{path.name}"

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_BACKUP_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_BACKUP_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3}),
    )
    client.put_object(
        Bucket=os.environ["R2_BACKUP_BUCKET"],
        Key=key,
        Body=path.read_bytes(),
        ContentType="application/json",
    )
    return key


if __name__ == "__main__":
    sys.exit(main())
