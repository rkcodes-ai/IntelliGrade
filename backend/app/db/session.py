"""
Async SQLAlchemy engine/session factory + FastAPI dependency.

Uses SQLAlchemy 2.x's async API with `asyncpg` as the driver.
"""

import time
from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
    connect_args={"timeout": settings.DATABASE_CONNECT_TIMEOUT_SECONDS},
)

# Module 08: slow-query logging. `before_cursor_execute`/`after_cursor_execute`
# are the sync engine's own events — SQLAlchemy's async engine wraps a sync
# engine internally (`engine.sync_engine`), so listening there is the
# documented way to observe every statement regardless of the async driver.
# Purely an observability hook: it never touches query results or behavior,
# only measures and logs.
if settings.SLOW_QUERY_THRESHOLD_MS > 0:

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        start_times = conn.info.get("query_start_time")
        if not start_times:
            return
        duration_ms = (time.perf_counter() - start_times.pop()) * 1000
        if duration_ms >= settings.SLOW_QUERY_THRESHOLD_MS:
            logger.warning(
                "slow_query",
                duration_ms=round(duration_ms, 2),
                statement=statement[:500],
            )


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """Used by the readiness probe to verify DB connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("database_health_check_failed", error=str(exc))
        return False
