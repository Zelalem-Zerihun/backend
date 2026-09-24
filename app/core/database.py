"""
Async SQLAlchemy engine, session factory, and declarative Base.

Usage in route handlers / services::

    from app.core.database import get_async_session

    @router.get("/example")
    async def example(session: AsyncSession = Depends(get_async_session)):
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Engine ───────────────────────────────────────────────────────────────
# pool_pre_ping:  verify connections before checkout (guards against PG restarts)
# echo:           mirror SQL to stdout when DEBUG=true (off in production)
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ── Session Factory ──────────────────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative Base ─────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.

    All models inherit from this class so Alembic's ``target_metadata``
    can discover them automatically.
    """

    pass


# ── FastAPI Dependency ───────────────────────────────────────────────────
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an ``AsyncSession`` scoped to a single request.

    The session is committed automatically if the request succeeds and
    rolled back on any unhandled exception, then closed in the ``finally``
    block regardless.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
