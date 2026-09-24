"""
Alembic environment configuration – async-compatible.

This file wires Alembic to our application's async SQLAlchemy engine
and ``Base.metadata`` so that ``alembic revision --autogenerate``
can diff the live database against our ORM models.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings

# Importing the models package forces all models to register on Base.metadata
from app.models import *  # noqa: F401, F403
from app.core.database import Base

# ── Alembic Config object ───────────────────────────────────────────────
config = context.config

# Inject the database URL from our centralized settings
# (replaces the placeholder in alembic.ini)
config.set_main_option("sqlalchemy.url", settings.async_database_url)

# Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point autogenerate at our declarative Base
target_metadata = Base.metadata


# ── Offline mode (SQL script generation, no live DB) ────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Emits SQL to stdout / a file without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (async engine against a live database) ──────────────────
def do_run_migrations(connection: Connection) -> None:
    """Run migrations within a synchronous connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine, connect, and run migrations.

    Uses ``NullPool`` so Alembic doesn't interfere with the
    application's own connection pool.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry-point for online mode – delegates to the async runner."""
    asyncio.run(run_async_migrations())


# ── Dispatch ─────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
