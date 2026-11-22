"""API tests for the TOTP second factor (#1177), with real tokens end to end."""

from datetime import datetime, timedelta, timezone

import pyotp
from httpx import AsyncClient
from sqlalchemy import select, update

from rs_api.api.auth import mfa as mfa_router
from rs_shared.core.infrastructure.security import (
    create_access_token,
    decode_access_token,
)
from rs_shared.models import AuditLog, MfaChallenge, RefreshToken, User, UserMfa

ADMIN_PASSWORD = "adminpassword"  # noqa: S105 -- the admin_user fixture's  # pragma: allowlist secret


def _code(secret: str, offset: int = 0) -> str:
    return pyotp.TOTP(secret).at(datetime.now(timezone.utc), counter_offset=offset)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str, password: str = ADMIN_PASSWORD):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _enrol(client: AsyncClient, admin: User) -> tuple[str, str, list[str]]:
    """Log in, enrol for real. Returns (secret, mfa access token, recovery codes)."""
    token = (await _login(client, admin.email)).json()["access_token"]
    start = await client.post("/auth/mfa/enrol/start", headers=_bearer(token))
    secret = start.json()["secret"]
    confirm = await client.post(
        "/auth/mfa/enrol/confirm",
        json={"code": _code(secret)},
        headers=_bearer(token),
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    return secret, body["access_token"], body["recovery_codes"]


async def _audit_actions(session_local_factory) -> list[str]:
    async with session_local_factory() as s:
        return [r[0] for r in (await s.execute(select(AuditLog.action))).all()]  # pyright: ignore[reportArgumentType]


async def test_admin_without_mfa_is_sent_to_enrol(
    unauthenticated_client: AsyncClient, admin_user: User
):
    login = await _login(unauthenticated_client, admin_user.email)
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert decode_access_token(token)["mfa"] is False  # pyright: ignore[reportOptionalSubscript]

    blocked = await unauthenticated_client.get(
        "/api/admin/overview", headers=_bearer(token)
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "mfa_enrollment_required"

    start = await unauthenticated_client.post(
        "/auth/mfa/enrol/start", headers=_bearer(token)
    )
    assert start.status_code == 200
    assert start.json()["otpauth_uri"].startswith("otpauth://totp/")


async def test_enrolment_unlocks_admin_and_revokes_other_sessions(
    unauthenticated_client: AsyncClient, admin_user: User, session_local_factory
):
    other = (await _login(unauthenticated_client, admin_user.email)).json()
    _, token, codes = await _enrol(unauthenticated_client, admin_user)

    assert len(codes) == 10
    assert decode_access_token(token)["mfa"] is True  # pyright: ignore[reportOptionalSubscript]
    ok = await unauthenticated_client.get("/api/admin/overview", headers=_bearer(token))
    assert ok.status_code == 200
    # The session that logged in separately before enrolment is gone.
    revoked = await unauthenticated_client.get(
        "/api/admin/overview", headers=_bearer(other["access_token"])
    )
    assert revoked.status_code == 401
    assert "mfa_enrolled" in await _audit_actions(session_local_factory)


async def test_login_with_mfa_needs_code_before_any_token(
    unauthenticated_client: AsyncClient, admin_user: User, session_local_factory
):
    secret, _, _ = await _enrol(unauthenticated_client, admin_user)
    async with session_local_factory() as s:
        before = len((await s.execute(select(RefreshToken.id))).all())  # pyright: ignore[reportArgumentType]

    login = await _login(unauthenticated_client, admin_user.email)
    body = login.json()
    assert login.status_code == 200
    assert body["mfa_required"] is True and body["access_token"] is None
    assert "refresh_token" not in login.headers.get("set-cookie", "")
    async with session_local_factory() as s:
        assert len((await s.execute(select(RefreshToken.id))).all()) == before  # pyright: ignore[reportArgumentType]

    wrong = "000000" if _code(secret, 1) != "000000" else "111111"
    bad = await unauthenticated_client.post(
        "/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": wrong}
    )
    assert bad.status_code == 401
    assert bad.json()["detail"] == "invalid_mfa_code"

    good = await unauthenticated_client.post(
        "/auth/mfa/verify",
        json={"mfa_token": body["mfa_token"], "code": _code(secret, 1)},
    )
    assert good.status_code == 200, good.text
    assert good.headers["cache-control"] == "no-store"
    assert "refresh_token=" in good.headers.get("set-cookie", "")
    # The session the code step opened is MFA-verified: admin routes serve it.
    token = good.json()["access_token"]
    assert decode_access_token(token)["mfa"] is True  # pyright: ignore[reportOptionalSubscript]
    overview = await unauthenticated_client.get(
        "/api/admin/overview", headers=_bearer(token)
    )
    assert overview.status_code == 200
    assert "mfa_verify_failed" in await _audit_actions(session_local_factory)
    assert "admin_login" in await _audit_actions(session_local_factory)


async def test_verify_with_recovery_code(
    unauthenticated_client: AsyncClient, admin_user: User
):
    _, _, codes = await _enrol(unauthenticated_client, admin_user)
    challenge = (await _login(unauthenticated_client, admin_user.email)).json()

    resp = await unauthenticated_client.post(
        "/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "recovery_code": codes[3]},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_verify_unknown_challenge(unauthenticated_client: AsyncClient):
    resp = await unauthenticated_client.post(
        "/auth/mfa/verify", json={"mfa_token": "bogus", "code": "123456"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "mfa_challenge_expired"


async def test_enrol_twice_conflicts(
    unauthenticated_client: AsyncClient, admin_user: User
):
    _, token, _ = await _enrol(unauthenticated_client, admin_user)
    again = await unauthenticated_client.post(
        "/auth/mfa/enrol/start", headers=_bearer(token)
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "mfa_already_enabled"


async def test_regenerate_recovery_codes(
    unauthenticated_client: AsyncClient, admin_user: User
):
    secret, token, old = await _enrol(unauthenticated_client, admin_user)
    resp = await unauthenticated_client.post(
        "/auth/mfa/recovery-codes",
        json={"code": _code(secret, 1)},
        headers=_bearer(token),
    )
    assert resp.status_code == 200
    assert not set(resp.json()["recovery_codes"]) & set(old)


async def test_non_admin_cannot_enrol(
    unauthenticated_client: AsyncClient, approved_company_user: User
):
    token = create_access_token(
        data={
            "sub": str(approved_company_user.id),
            "email": approved_company_user.email,
            "role": approved_company_user.role.value,
        }
    )
    resp = await unauthenticated_client.post(
        "/auth/mfa/enrol/start", headers=_bearer(token)
    )
    assert resp.status_code == 403


async def test_verify_is_rate_limited(unauthenticated_client: AsyncClient):
    mfa_router.limiter.enabled = True
    mfa_router.limiter._storage.reset()
    try:
        statuses = [
            (
                await unauthenticated_client.post(
                    "/auth/mfa/verify", json={"mfa_token": "x", "code": "123456"}
                )
            ).status_code
            for _ in range(11)
        ]
    finally:
        mfa_router.limiter._storage.reset()
        mfa_router.limiter.enabled = False
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


async def test_expired_challenge_rows_are_not_left_usable(
    unauthenticated_client: AsyncClient, admin_user: User, session_local_factory
):
    """A successful verify deletes the challenge (single-use)."""
    secret, _, _ = await _enrol(unauthenticated_client, admin_user)
    challenge = (await _login(unauthenticated_client, admin_user.email)).json()
    await unauthenticated_client.post(
        "/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "code": _code(secret, 1)},
    )
    async with session_local_factory() as s:
        assert (await s.execute(select(MfaChallenge))).first() is None


async def test_enrolled_session_survives_refresh(
    unauthenticated_client: AsyncClient, admin_user: User
):
    """The enrolling session was marked verified, so rotation keeps it usable."""
    await _enrol(unauthenticated_client, admin_user)
    refreshed = await unauthenticated_client.post("/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    token = refreshed.json()["access_token"]
    assert decode_access_token(token)["mfa"] is True  # pyright: ignore[reportOptionalSubscript]
    ok = await unauthenticated_client.get("/api/admin/overview", headers=_bearer(token))
    assert ok.status_code == 200


async def test_mfa_responses_are_never_cached(
    unauthenticated_client: AsyncClient, admin_user: User
):
    token = (await _login(unauthenticated_client, admin_user.email)).json()[
        "access_token"
    ]
    start = await unauthenticated_client.post(
        "/auth/mfa/enrol/start", headers=_bearer(token)
    )
    assert start.headers["cache-control"] == "no-store"


async def test_status_reports_codes_left(
    unauthenticated_client: AsyncClient, admin_user: User
):
    _, token, codes = await _enrol(unauthenticated_client, admin_user)
    challenge = (await _login(unauthenticated_client, admin_user.email)).json()
    used = await unauthenticated_client.post(
        "/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "recovery_code": codes[0]},
    )
    resp = await unauthenticated_client.get(
        "/auth/mfa/status", headers=_bearer(used.json()["access_token"])
    )
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True, "recovery_codes_remaining": 9}


async def test_verify_needs_exactly_one_kind_of_code(
    unauthenticated_client: AsyncClient,
):
    for body in (
        {"mfa_token": "x"},
        {"mfa_token": "x", "code": "123456", "recovery_code": "abcde-fghjk"},
    ):
        resp = await unauthenticated_client.post("/auth/mfa/verify", json=body)
        assert resp.status_code == 422


async def test_locked_account_gets_429(
    unauthenticated_client: AsyncClient, admin_user: User, session_local_factory
):
    secret, _, _ = await _enrol(unauthenticated_client, admin_user)
    async with session_local_factory() as s:
        await s.execute(
            update(UserMfa).values(
                locked_until=datetime.now(timezone.utc) + timedelta(minutes=5)
            )
        )
        await s.commit()
    challenge = (await _login(unauthenticated_client, admin_user.email)).json()
    resp = await unauthenticated_client.post(
        "/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "code": _code(secret, 1)},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "mfa_locked"
    assert resp.headers["Retry-After"] == "300"
