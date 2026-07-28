"""Alembic environment.

The database URL is never written into alembic.ini — it comes from the same Settings
object the app uses, so a migration always targets whatever DATABASE_URL points at
(SQLite locally, Railway Postgres in production) with no second source of truth and no
credentials in a committed file.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Running `alembic` from backend/ puts alembic/ on sys.path, not backend/ itself.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: F401,E402  (importing registers the tables on Base)
from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402
from app.models import UtcDateTime  # noqa: E402

config = context.config


def render_item(type_, obj, autogen_context) -> str | bool:
    """Emit UtcDateTime as the plain SQLAlchemy type it compiles to.

    Autogenerate would otherwise write `app.models.UtcDateTime()` into the migration,
    which makes a committed migration depend on application code — and break the day
    that class is renamed or moved. At the DDL level UtcDateTime *is*
    DateTime(timezone=True); its conversion logic only matters at runtime.
    """
    if type_ == "type" and isinstance(obj, UtcDateTime):
        autogen_context.imports.add("import sqlalchemy as sa")
        return "sa.DateTime(timezone=True)"
    return False

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().sqlalchemy_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot ALTER most columns in place; batch mode rewrites the table.
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            render_item=render_item,
            # Catch type drift, not only added and removed columns.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
