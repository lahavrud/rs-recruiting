# ruff: noqa: E402  -- env var must be set before src imports (see _TEST_JWT_SECRET below)
"""Shared pytest fixtures for all tests."""

import base64 as _base64
import os
import struct as _struct
import zlib as _zlib
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Single source of truth for the test JWT secret.
# Set with os.environ[] (not setdefault) so it always wins over any value that
# might already be in the environment, and so every xdist worker process gets
# the same predictable value at import time — before settings is loaded.
_TEST_JWT_SECRET = "test-secret-key-min-32-chars-for-testing!"
os.environ["JWT_SECRET_KEY"] = _TEST_JWT_SECRET

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import (
    get_current_admin,
    get_current_company,
    get_current_user,
)
from src.core.infrastructure.security import get_password_hash
from src.core.infrastructure.transactions import transactional
from src.enums import ApplicationStatus, JobStatus, UserRole
from src.main import app
from src.models import (
    ActivationToken,  # noqa: F401  -- force SQLModel registration before create_all
    Application,
    AuditLog,  # noqa: F401
    CandidateProfile,
    CompanyProfile,
    DataExportRequest,  # noqa: F401 -- Sprint 11 / #608
    InviteToken,  # noqa: F401
    Job,
    PasswordResetToken,  # noqa: F401
    RefreshToken,  # noqa: F401
    User,
)
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth.registration import (
    CompanyRegistrationData,
    register_company_user,
)

_EMAIL_TASK_TARGETS = [
    "src.services.auth.registration.enqueue_email_task",
    "src.services.auth.candidate_registration.enqueue_email_task",
    "src.services.auth.password_reset.enqueue_email_task",
    "src.services.admin.companies.enqueue_email_task",
    "src.services.admin.company_approval.enqueue_email_task",
    "src.services.admin.invites.enqueue_email_task",
    "src.services.admin._job_close.enqueue_email_task",
    "src.services.admin.jobs_workflow.enqueue_email_task",
    "src.services.company.jobs.enqueue_email_task",
    "src.services.public.applications.enqueue_email_task",
    "src.services.public._application_helpers.enqueue_email_task",
    "src.api.admin.applications.enqueue_email_task",
    "src.api.auth.activation.enqueue_email_task",
]


@pytest.fixture(scope="session", autouse=True)
def _fast_bcrypt_for_tests():
    """Reduce bcrypt cost factor in tests from 12 (~250ms) to 4 (~1ms).

    The default cost of 12 is fine for prod but multiplied across every
    test that creates a User (admin, company, candidate fixtures + the
    register / login / password-reset flows) it dominated local pytest
    runtime. Real bcrypt behavior is preserved (is_password_valid still
    works, hashes round-trip correctly) — we only lower the work factor.
    """
    import bcrypt

    _original = bcrypt.gensalt
    bcrypt.gensalt = lambda rounds=12, prefix=b"2b": _original(  # noqa: E731
        rounds=4, prefix=prefix
    )
    yield
    bcrypt.gensalt = _original


@pytest.fixture(autouse=True)
def mock_enqueue_email():
    """Patch enqueue_email_task in every service module for all tests.

    Prevents any test from trying to connect to Redis. Each service imports
    enqueue_email_task with 'from src.core.tasks import ...', creating a local
    binding, so each module must be patched individually.
    """
    patches = [patch(target, new_callable=AsyncMock) for target in _EMAIL_TASK_TARGETS]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


# Resume-matching enqueue bindings. Module-level imports must be patched at
# their binding site; ``src.services.candidate.profile`` imports lazily inside
# the function so patching the source in ``src.core.tasks`` covers it.
_MATCH_EMBED_TASK_TARGETS = [
    "src.core.tasks.enqueue_match_candidate_task",
    "src.core.tasks.enqueue_embed_job_task",
    "src.services.public.applications.enqueue_match_candidate_task",
    "src.services.admin.jobs.enqueue_embed_job_task",
    "src.services.admin.jobs_workflow.enqueue_embed_job_task",
]


@pytest.fixture(autouse=True)
def mock_enqueue_matching():
    """Neutralize embed/match enqueues so unrelated flows (apply, resume upload,
    job approve/edit) don't kick off real background matching during tests.

    Tests that exercise the matching tasks themselves call the task functions
    directly and are unaffected by this.
    """
    patches = [
        patch(target, new_callable=AsyncMock) for target in _MATCH_EMBED_TASK_TARGETS
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


class FakeEmbeddingProvider:
    """Deterministic, network-free embedding provider for tests.

    Hashes whitespace tokens into a fixed-width unit vector so that texts
    sharing words land close in cosine space — enough to assert match ranking
    without any real model. Mirrors how the email/storage fakes stand in for
    their real providers.
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim

    async def embed(
        self, texts: list[str], *, input_type: str = "search_document"
    ) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        import hashlib
        import math

        vec = [0.0] * self.dim
        for token in text.lower().split():
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


@pytest.fixture
def fake_embeddings():
    """Patch ``get_embedding_provider`` at its source with a deterministic fake.

    Opt-in (not autouse): only matching-task tests need it. Patching the source
    module covers the tasks' lazy ``from ... import get_embedding_provider``.
    """
    provider = FakeEmbeddingProvider(dim=settings.embedding_dim)
    with patch(
        "src.core.services.embeddings.get_embedding_provider", return_value=provider
    ):
        yield provider


@pytest.fixture(autouse=True)
def _provide_post_commit_hooks_context():
    """Establish an empty post-commit hooks contextvar for every test.

    Tests that bypass routes and call services directly never enter
    transactional() — without this, defer_after_commit() would raise
    RuntimeError. Tests that need the deferred hooks to actually execute
    (so that @patch mocks observe the calls) should still wrap their service
    call in transactional() inside the test body, where mocks are active.
    Tests that don't care whether the hook runs are unaffected.
    """
    from src.core.infrastructure.transactions import _post_commit_hooks

    token = _post_commit_hooks.set([])
    try:
        yield
    finally:
        _post_commit_hooks.reset(token)


@pytest.fixture
def mock_password_reset_rate_limit():
    """Disable the per-email password-reset rate limit in tests.

    The real implementation increments a Redis counter — across multiple test
    runs against a shared local Redis, a victim email accumulates count and
    the limit starts rejecting tokens, surfacing as flaky test failures.

    Not autouse: only the two test files that exercise the password-reset
    flow need this. Those files declare a module-level autouse fixture that
    pulls this one in (see tests/api/test_password_reset.py and
    tests/services/test_password_reset.py).
    """
    with patch(
        "src.services.auth.password_reset._per_email_rate_limit_ok",
        new_callable=AsyncMock,
        return_value=True,
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_lockout_db_writes():
    """Prevent _record_failed_attempt and _clear_failed_attempts from writing
    to the test DB via independent sessions, which bypass test-transaction rollback.

    Tests that specifically test lockout or failed-attempt accounting should
    override these mocks locally.
    """
    with (
        patch(
            "src.services.auth.login._record_failed_attempt",
            new_callable=AsyncMock,
        ),
        patch(
            "src.services.auth.login._clear_failed_attempts",
            new_callable=AsyncMock,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_invite_tokens():
    """Patch invite token functions for all tests.

    validate_invite_token is a no-op (any token is valid). Tests that want
    to test rejection configure the mock via the returned fixture value.
    """
    with (
        patch(
            "src.api.auth.registration.validate_invite_token", new_callable=AsyncMock
        ) as mock_validate,
        patch("src.api.auth.invites.validate_invite_token", new_callable=AsyncMock),
        patch(
            "src.services.admin.invites.generate_invite_token",
            new_callable=AsyncMock,
            return_value=(
                "test-invite-token-raw",
                "test-invite-token-abc123",
                datetime(2099, 1, 1, tzinfo=timezone.utc),
            ),
        ),
    ):
        yield mock_validate


@pytest.fixture(autouse=True)
def mock_storage_provider():
    """Patch storage provider for all tests — prevents real S3/disk uploads."""
    mock = MagicMock()
    mock.upload_file = AsyncMock(return_value="logos/test-logo.png")
    with patch(
        "src.services.auth.registration.get_storage_provider", return_value=mock
    ):
        yield mock


_BASE_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/rs_recruitment",
)

# Every run (solo or xdist) gets its own isolated database so tests never
# touch the dev DB. Solo runs use <dbname>_test; xdist workers use <dbname>_gw0 etc.
WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "master")


def _per_worker_url(base_url: str, worker_id: str) -> str:
    suffix = "test" if worker_id == "master" else worker_id
    base, sep, dbname = base_url.rpartition("/")
    db_only, qs_sep, qs = dbname.partition("?")
    return f"{base}{sep}{db_only}_{suffix}{qs_sep}{qs}"


def _admin_url(base_url: str) -> str:
    """URL for the postgres maintenance DB — used to CREATE/DROP per-worker DBs."""
    base, sep, dbname = base_url.rpartition("/")
    _db_only, qs_sep, qs = dbname.partition("?")
    return f"{base}{sep}postgres{qs_sep}{qs}"


def _per_worker_dbname(base_url: str, worker_id: str) -> str:
    _, _, dbname = base_url.rpartition("/")
    db_only, _, _ = dbname.partition("?")
    suffix = "test" if worker_id == "master" else worker_id
    return f"{db_only}_{suffix}"


TEST_DATABASE_URL = _per_worker_url(_BASE_DATABASE_URL, WORKER_ID)

# Several test modules read DATABASE_URL directly at import time to build their
# own engines (tests/api/test_auth.py, tests/core/infrastructure/test_dependencies.py,
# etc.). Rewrite the env var here so those reads pick up the per-worker URL too.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

test_engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool
)

TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def _create_tables_once() -> None:
    """Create all tables on the per-worker DB. Called once per worker, not per test."""
    from sqlalchemy import text

    async with test_engine.begin() as conn:
        # Required before create_all can build the pgvector ``embedding`` columns
        # (the schema is built from models here, not via the alembic migration).
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(SQLModel.metadata.create_all)


@pytest.fixture(scope="session", autouse=True)
def setup_testing_environment():
    """Set up testing environment + isolated database before any tests run.

    Every run gets its own database (solo: <dbname>_test, xdist: <dbname>_gw0 …)
    so tests never touch the dev DB and workers cannot collide on cleanup.

    Table creation runs ONCE per worker — `create_all` is a no-op when tables
    exist but still does a metadata introspection roundtrip on every call, which
    adds up over hundreds of tests.
    """
    settings.testing = True

    import asyncio

    worker_dbname = _per_worker_dbname(_BASE_DATABASE_URL, WORKER_ID)
    admin_url = _admin_url(_BASE_DATABASE_URL)

    async def _create_db() -> None:
        engine = create_async_engine(
            admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text

                await conn.execute(text(f'DROP DATABASE IF EXISTS "{worker_dbname}"'))
                await conn.execute(text(f'CREATE DATABASE "{worker_dbname}"'))
        finally:
            await engine.dispose()

    async def _drop_db() -> None:
        engine = create_async_engine(
            admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text

                await conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                        f" WHERE datname = '{worker_dbname}'"
                    )
                )
                await conn.execute(text(f'DROP DATABASE IF EXISTS "{worker_dbname}"'))
        finally:
            await engine.dispose()

    asyncio.run(_create_db())
    asyncio.run(_create_tables_once())
    try:
        yield
    finally:
        asyncio.run(test_engine.dispose())
        asyncio.run(_drop_db())
        settings.testing = False


# Build the TRUNCATE statement once at import time — table list is constant.
_TRUNCATE_SQL: str | None = None


def _truncate_sql() -> str | None:
    """One-shot TRUNCATE for every SQLModel table, in dependency order.

    Returns None if there are no tables (defensive — shouldn't happen).
    RESTART IDENTITY resets sequences so IDs are stable across tests.
    CASCADE is defensive: with `sorted_tables` reversed it shouldn't fire,
    but it covers any future tables not yet in metadata's sort order.
    """
    global _TRUNCATE_SQL
    if _TRUNCATE_SQL is None:
        names = [f'"{t.name}"' for t in SQLModel.metadata.sorted_tables]
        if not names:
            return None
        _TRUNCATE_SQL = f"TRUNCATE {', '.join(names)} RESTART IDENTITY CASCADE"
    return _TRUNCATE_SQL


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[None, None]:
    """Reset DB state between tests via a single TRUNCATE statement.

    Replaces the prior per-test `metadata.create_all` (now session-scoped in
    `setup_testing_environment`) + N-table `delete()` loop. One TRUNCATE
    instead of N DELETEs cuts per-test cleanup from a linear-in-tables
    roundtrip count to a single statement.

    NOT autouse: pure-Pydantic / pure-template tests (e.g. `test_schemas.py`,
    `tests/templates/test_email.py`, `test_file_validation.py`) never touch
    the DB and shouldn't pay the TRUNCATE cost. Tests that DO touch the DB
    pull this in transitively via `session`, `admin_user`, `admin_client`,
    `company_client`, etc. — every fixture that writes to the DB declares
    `test_db` as a dependency. A direct test_db parameter is needed only by
    the handful of tests that bypass those fixtures and use `TestSessionLocal`
    inline.
    """
    yield
    sql = _truncate_sql()
    if sql is None:
        return
    from sqlalchemy import text

    async with test_engine.begin() as conn:
        await conn.execute(text(sql))


@pytest.fixture
async def session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session.

    Each test gets a fresh session. Data is cleaned up via test_db fixture.
    """
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def mock_s3_bucket():
    """Fixture providing mock S3 bucket configuration.

    Can be reused across multiple test files.
    """
    return {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
    }


# ==================== User Fixtures ====================


def _make_company_profile_create(name: str) -> CompanyProfileCreate:
    return CompanyProfileCreate(
        name=name,
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )


def _make_png() -> bytes:
    """Generate a minimal valid 1×1 white PNG for use in tests."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = _zlib.crc32(tag + data) & 0xFFFFFFFF
        return _struct.pack(">I", len(data)) + tag + data + _struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", _struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", _zlib.compress(b"\x00\xff\xff\xff"))
        + _chunk(b"IEND", b"")
    )


FAKE_PNG: bytes = _make_png()
FAKE_LOGO: bytes = FAKE_PNG
FAKE_SIG_B64: str = _base64.b64encode(FAKE_PNG).decode()

_STRONG_PASSWORD = "SecurePass1!"


@pytest.fixture
async def company_user(test_db) -> User:
    """Create a pending (inactive) company user for testing."""
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password=_STRONG_PASSWORD,
            company_profile=_make_company_profile_create("Test Company"),
        )
        async with transactional(session):
            result = await register_company_user(
                user_data,
                session,
                FAKE_LOGO,
                "logo.png",
                CompanyRegistrationData(
                    logo_content_type="image/png",
                    agreement_signature=FAKE_SIG_B64,
                ),
            )
        return result.user


@pytest.fixture
async def approved_company_user(test_db) -> User:
    """Create an approved (active) company user for testing."""
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="approved@test.com",
            password=_STRONG_PASSWORD,
            company_profile=_make_company_profile_create("Approved Company"),
        )
        async with transactional(session):
            result = await register_company_user(
                user_data,
                session,
                FAKE_LOGO,
                "logo.png",
                CompanyRegistrationData(
                    logo_content_type="image/png",
                    agreement_signature=FAKE_SIG_B64,
                ),
            )
        result.user.is_active = True
        await session.commit()
        return result.user


@pytest.fixture
async def company_profile(approved_company_user: User) -> CompanyProfile:
    """Get company profile for approved company user."""
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                CompanyProfile.user_id == approved_company_user.id
            )
        )
        return result.scalar_one()


@pytest.fixture
async def admin_user(test_db) -> User:
    """Create an admin user for testing."""
    async with TestSessionLocal() as session:
        admin = User(
            email="admin@test.com",
            hashed_password=get_password_hash("adminpassword"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


@pytest.fixture
async def company_with_user(session: AsyncSession) -> CompanyProfile:
    """Create a company user and profile for service layer testing."""
    user = User(
        email="company@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None

    company = CompanyProfile(
        user_id=user.id,
        name="Test Company",
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_email=user.email,
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    assert company.id is not None
    return company


# ==================== Job Fixtures ====================


_DEFAULT_REQUIREMENTS: list[dict] = [
    {"text": "5+ years Python experience"},
    {"text": "FastAPI fluency"},
    {"text": "PostgreSQL fundamentals"},
]


@pytest.fixture
async def pending_job(company_profile: CompanyProfile) -> Job:
    """Create a pending job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            short_description="Senior Python role on a small backend team.",
            description="We are looking for a senior Python developer...",
            requirements=list(_DEFAULT_REQUIREMENTS),
            tags=["Remote", "Senior"],
            location="Tel Aviv, Israel",
            salary_min=15000,
            salary_max=25000,
            status=JobStatus.PENDING_APPROVAL,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def published_job(company_profile: CompanyProfile) -> Job:
    """Create a published job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            short_description="Senior Python role on a small backend team.",
            description="We are looking for a senior Python developer...",
            requirements=list(_DEFAULT_REQUIREMENTS),
            tags=["Remote", "Senior"],
            location="Tel Aviv, Israel",
            salary_min=15000,
            salary_max=25000,
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def closed_job(company_profile: CompanyProfile) -> Job:
    """Create a closed job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Closed Position",
            short_description="An older role that has since been closed.",
            description="This position is closed",
            requirements=list(_DEFAULT_REQUIREMENTS),
            tags=[],
            location="N/A",
            salary_min=10000,
            salary_max=15000,
            status=JobStatus.CLOSED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


# ==================== Application Fixtures ====================


@pytest.fixture
async def candidate_profile(test_db) -> CandidateProfile:
    """Create a candidate profile for testing."""
    async with TestSessionLocal() as session:
        candidate = CandidateProfile(
            full_name="Jane Candidate",
            email="jane@candidate.com",
            phone="555-1234",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return candidate


@pytest.fixture
async def application(
    published_job: Job, candidate_profile: CandidateProfile
) -> Application:
    """Create a NEW application linking a candidate to a published job."""
    async with TestSessionLocal() as session:
        app_obj = Application(
            job_id=published_job.id,
            candidate_id=candidate_profile.id,
            status=ApplicationStatus.NEW,
        )
        session.add(app_obj)
        await session.commit()
        await session.refresh(app_obj)
        return app_obj


# ==================== API Client Fixtures ====================


async def override_get_session():
    """Override get_session dependency for tests."""
    async with TestSessionLocal() as session:
        yield session


def _apply_admin_overrides(admin_user: User) -> None:
    async def _current_user(
        credentials=None,  # noqa: ARG001
        session=None,  # noqa: ARG001
    ):
        return admin_user

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_admin] = _current_user


def _apply_company_overrides(company_user: User) -> None:
    async def _current_company():
        async with TestSessionLocal() as session:
            user = (
                await session.execute(
                    select(User).where(User.id == company_user.id)  # pyright: ignore[reportArgumentType]
                )
            ).scalar_one()
            company_profile = (
                await session.execute(
                    select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                        CompanyProfile.user_id == user.id
                    )
                )
            ).scalar_one()
            return (user, company_profile)

    app.dependency_overrides[get_current_company] = _current_company


async def _make_client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an AsyncClient bound to the FastAPI app under test.

    Caller is responsible for setting any auth dependency overrides BEFORE
    awaiting this generator's first yield, and the fixture wrapper handles
    tearing them down afterwards.
    """
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def company_client(
    approved_company_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Test client authenticated as a company user."""
    _apply_company_overrides(approved_company_user)
    async for client in _make_client():
        yield client


@pytest.fixture
async def admin_client(admin_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Test client authenticated as an admin user."""
    _apply_admin_overrides(admin_user)
    async for client in _make_client():
        yield client


@pytest.fixture
async def public_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client without authentication (for public endpoints)."""
    async for client in _make_client():
        yield client


# Legacy alias for backward compatibility
@pytest.fixture
async def client(company_client: AsyncClient) -> AsyncClient:
    """Legacy alias for company_client."""
    return company_client


@pytest.fixture
async def unauthenticated_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Client with no auth dependency overrides.

    Use to verify protected endpoints return 401 when called without a token.
    The session override IS applied so the request reaches the auth guard
    instead of failing at DB acquisition.
    """
    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def company_role_client(
    approved_company_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated as a COMPANY-role user (NOT admin).

    Use to verify admin-only endpoints return 403 when called with a
    valid token whose user has the wrong role. The `get_current_user`
    dep is overridden so the admin guard fires the role check.
    """

    async def _current_user(
        credentials=None,  # noqa: ARG001
        session=None,  # noqa: ARG001
    ):
        return approved_company_user

    app.dependency_overrides[get_current_user] = _current_user
    async for client in _make_client():
        yield client
