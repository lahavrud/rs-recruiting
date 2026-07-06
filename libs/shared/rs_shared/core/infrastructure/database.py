"""Database configuration and async engine setup."""

import asyncio
import logging
import socket
from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rs_shared.core.infrastructure.config import settings

# Import models to ensure they're registered with SQLModel.metadata
from rs_shared.models import SQLModel  # noqa: F401

logger = logging.getLogger(__name__)

# Reserved for future ad-hoc column migrations; schema changes are handled by Alembic.
_MIGRATIONS: list[str] = []

# Count of physical connections opened this process — see `_log_new_connection`.
_connections_opened = 0

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
    # Fail fast (loudly) when the pool is exhausted rather than hanging on the
    # SQLAlchemy 30 s default — a burst that saturates the pool then surfaces
    # as a logged TimeoutError we can alarm on. See _log_pool_pressure.
    pool_timeout=settings.db_pool_timeout,
    # Server-side TCP keepalives via a public asyncpg channel (Postgres GUCs
    # sent as startup parameters). The RDS backend's OS then probes the socket
    # every 60 s, generating traffic that keeps the AWS NAT Gateway mapping
    # (idle-TCP timeout ~350 s) alive so pooled connections don't silently die.
    # Belt-and-suspenders with the client-side socket opts in
    # `_set_tcp_keepalive` below (the latter reaches into asyncpg internals and
    # can no-op on a driver bump — this one can't).
    connect_args={
        "server_settings": {
            "tcp_keepalives_idle": "60",
            "tcp_keepalives_interval": "10",
            "tcp_keepalives_count": "5",
        }
    },
)


@event.listens_for(engine.sync_engine, "connect")
def _set_tcp_keepalive(dbapi_conn: object, _connection_record: object) -> None:
    # Client-side counterpart to the server_settings keepalives above: set the
    # opts directly on our end of the socket too. asyncpg doesn't expose this in
    # its public API, so we reach into the driver's private connection attr —
    # which means a driver bump can silently break it. That's exactly why the
    # failure path below logs at WARNING (not debug): a silent no-op here is how
    # pooled connections start dying and every request pays a fresh reconnect.
    try:
        raw = dbapi_conn._connection  # type: ignore[attr-defined]  # reaching into the DBAPI driver's private connection attr; not in the stubs
        sock: socket.socket | None = raw._protocol.transport.get_extra_info("socket")
        if sock is None:
            logger.warning("DB connection exposed no socket; TCP keepalive not set")
            return
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):  # Linux only
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
    except Exception:
        logger.warning(
            "Could not set client-side TCP keepalive on DB connection "
            "(asyncpg internals may have changed); relying on server_settings "
            "keepalives + pool_pre_ping",
            exc_info=True,
        )


@event.listens_for(engine.sync_engine, "connect")
def _log_new_connection(_dbapi_conn: object, _connection_record: object) -> None:
    # A new *physical* connection to RDS is expensive (TCP + TLS + auth). With a
    # warm pool this fires only while filling the pool; a steady stream of these
    # in the logs means connections are dying between requests (keepalives not
    # holding) and every request is paying a cold reconnect. Cheap churn signal.
    global _connections_opened
    _connections_opened += 1
    logger.info(
        "New DB connection opened (total opened this process: %d)",
        _connections_opened,
    )


@event.listens_for(engine.sync_engine, "checkout")
def _log_pool_pressure(
    _dbapi_conn: object, _connection_record: object, _connection_proxy: object
) -> None:
    # Distinguishes pool *exhaustion* from connection churn: when checkouts push
    # past pool_size into overflow, the pool is under pressure and requests are
    # at risk of the pool_timeout wait. If this warns during dashboard bursts,
    # the fix is a bigger pool / fewer parallel calls — not the keepalives.
    pool = engine.sync_engine.pool
    checked_out = pool.checkedout()  # type: ignore[attr-defined]  # QueuePool exposes checkedout(); base Pool typing doesn't
    if checked_out > settings.db_pool_size:
        logger.warning(
            "DB pool under pressure: %d checked out (pool_size=%d, using overflow)",
            checked_out,
            settings.db_pool_size,
        )


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


async def warm_up_pool() -> None:
    """Open the pool's base connections at startup, concurrently.

    Without this the first `db_pool_size` requests after a boot (or after an
    idle period drains the pool) each pay a full cold connect to RDS — TCP +
    TLS + auth — on the request path, which is exactly the multi-second
    "connect" latency the request traces showed. Filling the pool up front
    moves that cost off the hot path.

    Best-effort: a DB that's briefly unavailable at boot must not crash the
    app (the migrate/deploy gate handles real DB failures). We just log and
    let normal lazy connect + pool_pre_ping recover.
    """
    size = settings.db_pool_size
    if size <= 0:
        return

    async def _one() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.gather(*(_one() for _ in range(size)))
        logger.info("DB pool pre-warmed with %d connections", size)
    except Exception:
        logger.warning(
            "DB pool pre-warm failed; falling back to lazy connect", exc_info=True
        )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session() as session:
        yield session
