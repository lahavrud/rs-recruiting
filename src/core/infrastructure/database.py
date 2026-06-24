"""Database configuration and async engine setup."""

import logging
import socket
from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.infrastructure.config import settings

# Import models to ensure they're registered with SQLModel.metadata
from src.models import SQLModel  # noqa: F401

logger = logging.getLogger(__name__)

# Reserved for future ad-hoc column migrations; schema changes are handled by Alembic.
_MIGRATIONS: list[str] = []

# Database URL - uses config which reads from environment variables
DATABASE_URL = settings.database_url

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    # Log SQL queries (configurable via DATABASE_ECHO env var)
    echo=settings.database_echo,
    future=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_tcp_keepalive(dbapi_conn: object, _connection_record: object) -> None:
    # asyncpg doesn't expose TCP keepalives in its public API; set them
    # directly on the socket so AWS NAT Gateway (idle-TCP timeout ~350 s)
    # never silently drops pooled connections.  pool_pre_ping catches the
    # rare case where a connection dies despite keepalives.
    try:
        raw = dbapi_conn._connection  # type: ignore[attr-defined]  # reaching into the DBAPI driver's private connection attr; not in the stubs
        sock: socket.socket | None = raw._protocol.transport.get_extra_info("socket")
        if sock is None:
            return
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):  # Linux only
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
    except Exception:
        logger.debug("Could not set TCP keepalive on DB connection", exc_info=True)


# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database tables and apply lightweight column migrations."""
    async with engine.begin() as conn:
        # Required before create_all can build the pgvector `embedding` columns.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(SQLModel.metadata.create_all)
        for stmt in _MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception:
                logger.exception("Migration failed: %s", stmt)
                raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session() as session:
        yield session
