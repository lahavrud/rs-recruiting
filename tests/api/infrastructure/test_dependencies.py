"""Tests for authentication dependencies."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import (
    _is_trusted_proxy,
    client_ip,
    get_current_admin,
    get_current_admin_pre_mfa,
    get_current_candidate,
    get_current_user,
    get_token_payload,
)
from rs_shared.core.infrastructure.security import (
    create_access_token,
    decode_access_token,
)
from rs_shared.enums import UserRole
from rs_shared.models import CandidateProfile, RefreshToken, User, UserMfa


@pytest.fixture
async def active_user(session: AsyncSession):
    """Create an active test user."""
    from rs_shared.core.infrastructure.security import get_password_hash

    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


class MockCredentials:
    """Mock HTTPAuthorizationCredentials for testing."""

    def __init__(self, token: str):
        self.credentials = token


def _make_payload(token: str) -> dict:
    """Decode a token and return the payload (no blacklist check)."""
    payload = decode_access_token(token)
    assert payload is not None, "Token must be valid to build payload"
    return payload


@pytest.mark.asyncio
async def test_get_current_user_invalid_user_id_type(
    session: AsyncSession, active_user: User
):
    """Test that invalid user_id type in JWT token returns 401, not 500."""
    invalid_token = create_access_token(
        data={"sub": "not_a_number", "email": "test@example.com", "role": "COMPANY"}
    )
    payload = _make_payload(invalid_token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(payload=payload, session=session)

    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_none_user_id(session: AsyncSession):
    """Test that None user_id in JWT token returns 401."""
    invalid_token = create_access_token(
        data={"email": "test@example.com", "role": "COMPANY"}
    )
    payload = _make_payload(invalid_token)
    # Remove 'sub' to simulate missing user_id
    payload.pop("sub", None)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(payload=payload, session=session)

    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_valid_token(session: AsyncSession, active_user: User):
    """Test that valid JWT token with correct user_id type works."""
    valid_token = create_access_token(
        data={
            "sub": str(active_user.id),
            "email": active_user.email,
            "role": active_user.role.value,
        }
    )
    payload = _make_payload(valid_token)
    user = await get_current_user(payload=payload, session=session)

    assert user.id == active_user.id
    assert user.email == active_user.email
    assert user.is_active is True


async def _session_row(session: AsyncSession, user: User, *, verified: bool) -> int:
    row = RefreshToken(
        token_hash=f"dep-{verified}-{user.id}",
        user_id=user.id,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        mfa_verified=verified,
    )
    session.add(row)
    await session.commit()
    assert row.id is not None
    return row.id


def _payload_for(user: User, sid: int | None) -> dict:
    data = {"sub": str(user.id), "email": user.email, "role": user.role.value}
    if sid is not None:
        data["sid"] = sid
    return _make_payload(create_access_token(data=data))


@pytest.mark.asyncio
async def test_mfa_user_is_served_only_by_a_verified_session(
    session: AsyncSession, active_user: User
):
    """#1177: with MFA on, a session that never passed the code is refused,
    however fresh its token, and so is a token with no session at all."""
    session.add(
        UserMfa(
            user_id=active_user.id,
            secret_encrypted="ct",
            enabled_at=datetime.now(timezone.utc),
        )
    )
    verified = await _session_row(session, active_user, verified=True)
    unverified = await _session_row(session, active_user, verified=False)

    user = await get_current_user(
        payload=_payload_for(active_user, verified), session=session
    )
    assert user.id == active_user.id
    for sid in (unverified, None):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                payload=_payload_for(active_user, sid), session=session
            )
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "session_revoked"


@pytest.mark.asyncio
async def test_unverified_session_is_fine_without_mfa(
    session: AsyncSession, active_user: User
):
    sid = await _session_row(session, active_user, verified=False)
    user = await get_current_user(
        payload=_payload_for(active_user, sid), session=session
    )
    assert user.id == active_user.id


@pytest.mark.asyncio
async def test_get_current_user_inactive_user(session: AsyncSession):
    """Test that inactive user cannot authenticate."""
    from rs_shared.core.infrastructure.security import get_password_hash

    inactive_user = User(
        email="inactive@example.com",
        hashed_password=get_password_hash("testpassword"),
        role=UserRole.COMPANY,
        is_active=False,
    )
    session.add(inactive_user)
    await session.commit()
    await session.refresh(inactive_user)

    token = create_access_token(
        data={
            "sub": str(inactive_user.id),
            "email": inactive_user.email,
            "role": inactive_user.role.value,
        }
    )
    payload = _make_payload(token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(payload=payload, session=session)

    assert exc_info.value.status_code == 403
    assert "inactive" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_token_payload_invalid_token():
    """Test that get_token_payload raises 401 for an invalid token."""
    credentials = MockCredentials("invalid.token.here")

    with pytest.raises(HTTPException) as exc_info:
        await get_token_payload(credentials=credentials)

    assert exc_info.value.status_code == 401


@pytest.fixture
async def admin_user(session: AsyncSession):
    """Create an active admin test user."""
    from rs_shared.core.infrastructure.security import get_password_hash

    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def company_user(session: AsyncSession):
    """Create an active company test user."""
    from rs_shared.core.infrastructure.security import get_password_hash

    user = User(
        email="company@example.com",
        hashed_password=get_password_hash("companypassword"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


class TestGetCurrentAdmin:
    """Tests for get_current_admin() dependency."""

    @pytest.mark.asyncio
    async def test_get_current_admin_admin_user_access(
        self, session: AsyncSession, admin_user: User
    ):
        """Test that admin user with valid token passes."""
        token = create_access_token(
            data={
                "sub": str(admin_user.id),
                "email": admin_user.email,
                "role": admin_user.role.value,
            }
        )
        payload = _make_payload(token)
        current_user = await get_current_user(payload=payload, session=session)
        session.add(
            UserMfa(
                user_id=admin_user.id,
                secret_encrypted="x",
                enabled_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

        admin = await get_current_admin(current_user=current_user, session=session)

        assert admin.id == admin_user.id
        assert admin.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_get_current_admin_without_mfa_must_enrol(
        self, session: AsyncSession, admin_user: User
    ):
        """An admin with no confirmed MFA is sent to enrol (#1177)."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(current_user=admin_user, session=session)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "mfa_enrollment_required"

    @pytest.mark.asyncio
    async def test_get_current_admin_pending_enrolment_must_enrol(
        self, session: AsyncSession, admin_user: User
    ):
        """A secret issued but never confirmed is not MFA."""
        session.add(UserMfa(user_id=admin_user.id, secret_encrypted="x"))
        await session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(current_user=admin_user, session=session)

        assert exc_info.value.detail == "mfa_enrollment_required"

    @pytest.mark.asyncio
    async def test_pre_mfa_admin_passes_without_mfa(self, admin_user: User):
        """Enrolment endpoints accept an admin before MFA exists."""
        assert await get_current_admin_pre_mfa(current_user=admin_user) is admin_user

    @pytest.mark.asyncio
    async def test_get_current_admin_non_admin_user_rejection(
        self, session: AsyncSession, company_user: User
    ):
        """Test that COMPANY role user raises 403 error."""
        token = create_access_token(
            data={
                "sub": str(company_user.id),
                "email": company_user.email,
                "role": company_user.role.value,
            }
        )
        payload = _make_payload(token)
        current_user = await get_current_user(payload=payload, session=session)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_pre_mfa(current_user=current_user)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_admin_invalid_token(
        self, session: AsyncSession, admin_user: User
    ):
        """Test that invalid token raises appropriate error."""
        credentials = MockCredentials("invalid.token.here")

        with pytest.raises(HTTPException) as exc_info:
            await get_token_payload(credentials=credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_admin_inactive_admin_user(self, session: AsyncSession):
        """Test inactive admin user handling."""
        from rs_shared.core.infrastructure.security import get_password_hash

        inactive_admin = User(
            email="inactive_admin@example.com",
            hashed_password=get_password_hash("adminpassword"),
            role=UserRole.ADMIN,
            is_active=False,
        )
        session.add(inactive_admin)
        await session.commit()
        await session.refresh(inactive_admin)

        token = create_access_token(
            data={
                "sub": str(inactive_admin.id),
                "email": inactive_admin.email,
                "role": inactive_admin.role.value,
            }
        )
        payload = _make_payload(token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(payload=payload, session=session)

        assert exc_info.value.status_code == 403
        assert "inactive" in exc_info.value.detail.lower()


@pytest.fixture
async def candidate_user_with_profile(session: AsyncSession):
    """Create an active candidate user with a linked profile."""
    from rs_shared.core.infrastructure.security import get_password_hash

    user = User(
        email="candidate-dep@example.com",
        hashed_password=get_password_hash("candpw"),
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    profile = CandidateProfile(
        user_id=user.id,  # type: ignore[arg-type]
        full_name="Dep Test Candidate",
        email="candidate-dep@example.com",
        phone="050-000-0001",
    )
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    await session.refresh(profile)
    return user, profile


class TestGetCurrentCandidate:
    """Tests for get_current_candidate() dependency."""

    @pytest.mark.asyncio
    async def test_candidate_user_access(
        self,
        session: AsyncSession,
        candidate_user_with_profile,
    ):
        """Candidate user with a linked profile passes; returns (user, profile)."""
        user, profile = candidate_user_with_profile
        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )
        payload = _make_payload(token)
        current_user = await get_current_user(payload=payload, session=session)
        ret_user, ret_profile = await get_current_candidate(
            current_user=current_user, session=session
        )
        assert ret_user.id == user.id
        assert ret_profile.id == profile.id

    @pytest.mark.asyncio
    async def test_company_user_rejected(
        self, session: AsyncSession, company_user: User
    ):
        """COMPANY-role token receives 403 from get_current_candidate."""
        token = create_access_token(
            data={
                "sub": str(company_user.id),
                "email": company_user.email,
                "role": company_user.role.value,
            }
        )
        payload = _make_payload(token)
        current_user = await get_current_user(payload=payload, session=session)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_candidate(current_user=current_user, session=session)

        assert exc_info.value.status_code == 403
        assert "candidate" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_admin_user_rejected(self, session: AsyncSession, admin_user: User):
        """ADMIN-role token receives 403 from get_current_candidate."""
        token = create_access_token(
            data={
                "sub": str(admin_user.id),
                "email": admin_user.email,
                "role": admin_user.role.value,
            }
        )
        payload = _make_payload(token)
        current_user = await get_current_user(payload=payload, session=session)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_candidate(current_user=current_user, session=session)

        assert exc_info.value.status_code == 403
        assert "candidate" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_candidate_without_profile_404(self, session: AsyncSession):
        """Candidate user without a linked profile returns 404 (defensive case)."""
        from rs_shared.core.infrastructure.security import get_password_hash

        user = User(
            email="cand-no-profile@example.com",
            hashed_password=get_password_hash("password"),
            role=UserRole.CANDIDATE,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )
        payload = _make_payload(token)
        current_user = await get_current_user(payload=payload, session=session)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_candidate(current_user=current_user, session=session)

        assert exc_info.value.status_code == 404


# ── client_ip / trusted-proxy guard (issue #647) ─────────────────────────────


def _make_request(peer: str | None, xff: str | None = None) -> MagicMock:
    req = MagicMock()
    req.client = MagicMock(host=peer) if peer else None
    headers: dict[str, str] = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    req.headers = headers
    return req


class TestIsTrustedProxy:
    def test_empty_config_never_trusted(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = ""
            assert _is_trusted_proxy("10.0.0.1") is False

    def test_exact_ip_match(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.1"
            assert _is_trusted_proxy("10.0.0.1") is True

    def test_cidr_match(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.0/8"
            assert _is_trusted_proxy("10.1.2.3") is True

    def test_cidr_no_match(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.0/8"
            assert _is_trusted_proxy("192.168.1.1") is False

    def test_multiple_cidrs_second_matches(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.0/8, 172.16.0.0/12"
            assert _is_trusted_proxy("172.20.0.5") is True

    def test_invalid_peer_ip_returns_false(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.0/8"
            assert _is_trusted_proxy("not-an-ip") is False


class TestClientIp:
    def test_no_trusted_proxy_ignores_xff(self):
        """Without trusted_proxy_ips configured, XFF is always ignored."""
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = ""
            req = _make_request("1.2.3.4", xff="9.9.9.9")
            assert client_ip(req) == "1.2.3.4"

    def test_trusted_peer_xff_used(self):
        """When peer is trusted, return leftmost XFF entry."""
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.0/8"
            req = _make_request("10.0.0.1", xff="203.0.113.5, 10.0.0.1")
            assert client_ip(req) == "203.0.113.5"

    def test_untrusted_peer_xff_ignored(self):
        """When peer is not trusted, fall back to peer IP even if XFF is set."""
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.0/8"
            req = _make_request("203.0.113.99", xff="1.1.1.1")
            assert client_ip(req) == "203.0.113.99"

    def test_no_client_returns_none(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = ""
            req = _make_request(None)
            assert client_ip(req) is None

    def test_trusted_peer_no_xff_falls_back_to_peer(self):
        """Trusted peer but no XFF header — return the peer IP."""
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.trusted_proxy_ips = "10.0.0.0/8"
            req = _make_request("10.0.0.1", xff=None)
            assert client_ip(req) == "10.0.0.1"


# ── client_ip behind CloudFront → API Gateway ────────────────────────────────


def _make_cf_request(
    viewer_address: str | None, peer: str = "10.0.1.57", xff: str | None = None
) -> MagicMock:
    req = _make_request(peer, xff=xff)
    if viewer_address is not None:
        req.headers["cloudfront-viewer-address"] = viewer_address
    return req


class TestClientIpCloudFrontViewerAddress:
    """Prod peers are API Gateway VPC-link ENIs shared by every client, so the
    CloudFront-set viewer address is the only per-client signal."""

    def test_viewer_address_used_when_origin_verify_enforced(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.origin_verify_secret = "secret"  # pragma: allowlist secret
            s.trusted_proxy_ips = ""
            req = _make_cf_request("203.0.113.7:51234")
            assert client_ip(req) == "203.0.113.7"

    def test_viewer_address_ipv6(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.origin_verify_secret = "secret"  # pragma: allowlist secret
            s.trusted_proxy_ips = ""
            req = _make_cf_request("2001:db8::1:443")
            assert client_ip(req) == "2001:db8::1"

    def test_viewer_address_wins_over_spoofed_xff(self):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.origin_verify_secret = "secret"  # pragma: allowlist secret
            s.trusted_proxy_ips = "10.0.0.0/16"
            req = _make_cf_request("203.0.113.7:51234", xff="1.1.1.1, 203.0.113.7")
            assert client_ip(req) == "203.0.113.7"

    def test_viewer_address_ignored_without_origin_verify(self):
        """Without CloudFront-only enforcement anyone could send the header."""
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.origin_verify_secret = None
            s.trusted_proxy_ips = ""
            req = _make_cf_request("203.0.113.7:51234", peer="198.51.100.9")
            assert client_ip(req) == "198.51.100.9"

    @pytest.mark.parametrize(
        "raw", ["", "not-an-ip:443", "203.0.113.7", "203.0.113.7:port", "2001:db8::1"]
    )
    def test_malformed_viewer_address_falls_back_to_peer(self, raw: str):
        with patch("rs_api.infrastructure.dependencies.settings") as s:
            s.origin_verify_secret = "secret"  # pragma: allowlist secret
            s.trusted_proxy_ips = ""
            req = _make_cf_request(raw, peer="10.0.1.57")
            assert client_ip(req) == "10.0.1.57"
