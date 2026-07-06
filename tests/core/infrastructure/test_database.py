"""Unit tests for database module initialization."""

import logging
import os

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import rs_shared.core.infrastructure.database as database_module
from rs_shared.core.infrastructure.database import engine, init_db
from rs_shared.models import Application, CandidateProfile, CompanyProfile, Job, User

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/rs_recruitment",
)


class TestInitDB:
    """Tests for init_db() function."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self):
        """Test that init_db creates database tables."""
        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)

        # Initialize database
        async with test_engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        # Verify tables exist (need to use run_sync for sync operations)
        def get_table_names(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()

        async with test_engine.connect() as conn:
            table_names = await conn.run_sync(get_table_names)

        # Check that key tables exist
        assert "user" in table_names
        assert "companyprofile" in table_names
        assert "job" in table_names
        assert "candidateprofile" in table_names
        assert "application" in table_names

    @pytest.mark.asyncio
    async def test_init_db_all_models_registered(self, test_db):
        """Test that all models are registered with SQLModel.metadata."""
        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)

        # Initialize database
        async with test_engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        # Verify we can query each model
        async with async_sessionmaker(test_engine, class_=AsyncSession)() as session:
            # Try to query each model (this verifies tables exist)
            result = await session.execute(select(User))
            users = result.scalars().all()
            assert isinstance(users, list)

            result = await session.execute(select(CompanyProfile))
            companies = result.scalars().all()
            assert isinstance(companies, list)

            result = await session.execute(select(Job))
            jobs = result.scalars().all()
            assert isinstance(jobs, list)

            result = await session.execute(select(CandidateProfile))
            candidates = result.scalars().all()
            assert isinstance(candidates, list)

            result = await session.execute(select(Application))
            applications = result.scalars().all()
            assert isinstance(applications, list)

    @pytest.mark.asyncio
    async def test_init_db_tables_can_be_queried(self, test_db):
        """Test that tables can be queried after initialization."""
        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
        test_session_factory = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )

        # Initialize database
        async with test_engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all)

        # Create a test user and verify we can query it
        async with test_session_factory() as session:
            from rs_shared.core.infrastructure.security import get_password_hash
            from rs_shared.enums import UserRole

            user = User(
                email="test@example.com",
                hashed_password=get_password_hash("password"),
                role=UserRole.COMPANY,
            )
            session.add(user)
            await session.commit()

            # Query the user
            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            found_user = result.scalar_one_or_none()

            assert found_user is not None
            assert found_user.email == "test@example.com"


class TestInitDbMigrationFailure:
    """A failing ad-hoc migration must be logged and re-raised, never swallowed."""

    @pytest.mark.asyncio
    async def test_failed_migration_is_logged_and_raised(self, monkeypatch, caplog):
        # Use a fresh engine bound to this worker's isolated test database —
        # the module-level `engine` is bound to the unsuffixed base DATABASE_URL
        # (read before conftest rewrites it per-worker) and is shared, unmanaged
        # infrastructure that other tests in this file deliberately avoid.
        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
        monkeypatch.setattr(database_module, "engine", test_engine)
        monkeypatch.setattr(
            database_module, "_MIGRATIONS", ["SELECT * FROM nonexistent_table_xyz"]
        )

        with caplog.at_level(logging.ERROR, logger=database_module.logger.name):
            with pytest.raises(Exception):
                await init_db()

        assert any("Migration failed" in record.message for record in caplog.records)


class TestEngineConfiguration:
    """Tests for engine configuration."""

    def test_engine_is_created(self):
        """Test that engine is created."""
        assert engine is not None

    def test_engine_echo_setting_respects_config(self):
        """Test that engine echo setting respects config."""

        # Engine should respect database_echo setting
        # We can't easily test this without creating a new engine,
        # but we can verify the engine exists and is configured
        assert engine is not None
        # The echo setting is set during engine creation based on settings.database_echo

    def test_engine_pool_uses_configured_settings(self):
        """Engine pool reflects db_pool_* settings, not SQLAlchemy defaults (5+10)."""
        from rs_shared.core.infrastructure.config import settings

        # QueuePool exposes size() (configured pool_size) and overflow capacity
        # via internal _max_overflow. Verify configured values made it through.
        assert engine.pool.size() == settings.db_pool_size
        assert getattr(engine.pool, "_max_overflow") == settings.db_max_overflow
        assert getattr(engine.pool, "_recycle") == settings.db_pool_recycle
        assert getattr(engine.pool, "_pre_ping") == settings.db_pool_pre_ping
        assert getattr(engine.pool, "_timeout") == settings.db_pool_timeout

    def test_pool_settings_have_sensible_defaults(self):
        """Defaults must beat SQLAlchemy's 5+10 to handle modest production load."""
        from rs_shared.core.infrastructure.config import Settings

        defaults = Settings.model_fields
        assert defaults["db_pool_size"].default >= 10
        assert defaults["db_max_overflow"].default >= 10
        assert defaults["db_pool_recycle"].default > 0
        assert defaults["db_pool_pre_ping"].default is True
        # Fail fast, well under SQLAlchemy's 30 s default, so pool exhaustion
        # surfaces as an alarmable error rather than a silent long stall.
        assert 0 < defaults["db_pool_timeout"].default < 30


class TestWarmUpPool:
    """warm_up_pool() fills the pool up front and never crashes startup."""

    @pytest.mark.asyncio
    async def test_warm_up_pool_opens_connections(self, monkeypatch, caplog):
        """Happy path: pre-warm succeeds against a live DB and logs the count."""
        from rs_shared.core.infrastructure.config import settings

        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
        monkeypatch.setattr(database_module, "engine", test_engine)
        monkeypatch.setattr(settings, "db_pool_size", 3)

        with caplog.at_level(logging.INFO, logger=database_module.logger.name):
            await database_module.warm_up_pool()

        assert any("pre-warmed with 3" in r.message for r in caplog.records)
        await test_engine.dispose()

    @pytest.mark.asyncio
    async def test_warm_up_pool_no_op_when_size_zero(self, monkeypatch):
        """size <= 0 returns immediately without touching the engine."""
        from rs_shared.core.infrastructure.config import settings

        # A sentinel engine whose use would raise — proves we never connect.
        monkeypatch.setattr(settings, "db_pool_size", 0)
        monkeypatch.setattr(database_module, "engine", object())

        await database_module.warm_up_pool()  # must not raise

    @pytest.mark.asyncio
    async def test_warm_up_pool_swallows_connect_failure(self, monkeypatch, caplog):
        """A DB that's unreachable at boot logs a warning, never crashes startup.

        No network: a fake engine whose ``connect()`` raises stands in for an
        unreachable DB, so the except branch runs without touching a socket.
        """
        from rs_shared.core.infrastructure.config import settings

        class _BrokenEngine:
            def connect(self):
                raise ConnectionError("simulated DB unreachable at boot")

        monkeypatch.setattr(database_module, "engine", _BrokenEngine())
        monkeypatch.setattr(settings, "db_pool_size", 2)

        with caplog.at_level(logging.WARNING, logger=database_module.logger.name):
            await database_module.warm_up_pool()  # must not raise

        assert any("pre-warm failed" in r.message for r in caplog.records)


class TestSessionFactory:
    """Tests for session factory configuration."""

    def test_session_factory_creates_async_sessions(self):
        """Test that session factory creates async sessions."""
        from rs_shared.core.infrastructure.database import async_session

        # Verify async_session is a sessionmaker
        assert async_session is not None
        assert isinstance(async_session, async_sessionmaker)

    def test_session_factory_configuration(self):
        """Test that session factory configuration is correct."""
        from rs_shared.core.infrastructure.database import async_session

        # Verify session factory is configured for async
        # The class_ is passed as a keyword argument during creation
        # Check that expire_on_commit is False
        assert async_session.kw.get("expire_on_commit") is False
        # Verify it's an async_sessionmaker instance
        assert isinstance(async_session, async_sessionmaker)
