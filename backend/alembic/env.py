"""
Alembic environment configuration.

Builds the database URL from `app.core.config.Settings` (single source of
truth shared with the running application) and uses `Base.metadata` for
autogeneration. Runs migrations through an async engine (`asyncpg`), driving
Alembic's sync migration machinery via `AsyncConnection.run_sync`.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Importing the aggregator registers every model module's tables on
# Base.metadata (required for autogeneration) and resolves the string-based
# relationship() forward references between them.
from app import models as _models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _ensure_wide_version_column(connection: Connection) -> None:
    """Widen alembic's own version_num column beyond its VARCHAR(32) default.

    This project's revision ids are descriptive filenames (e.g.
    ``0006_create_assessment_domain_tables``, 36 chars), which exceed
    Alembic's hardcoded default width and raise StringDataRightTruncationError
    on real Postgres (SQLite never enforces VARCHAR length, which is why this
    was invisible under the test suite). Alembic exposes no configure()
    option for this column's width, so the table is pre-created/widened here
    before Alembic's own checkfirst=True creation step runs. Only affects
    Alembic's internal bookkeeping table, not any application schema.
    """
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            "version_num VARCHAR(255) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
            ")"
        )
    )
    connection.execute(
        text(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(255)"
        )
    )


def do_run_migrations(connection: Connection) -> None:
    # Must run *after* configure(): configure() snapshots whether the
    # connection is already mid-transaction to decide if Alembic or the
    # caller owns the commit. Executing DDL before configure() would
    # autobegin a transaction first, flip that snapshot, and leave this
    # (never-committed) transaction silently discarded on connection close.
    context.configure(connection=connection, target_metadata=target_metadata)
    _ensure_wide_version_column(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live async DB connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
