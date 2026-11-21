# Auth Rules

## Token model
- Access token: 10min TTL, stored in `localStorage`
- Refresh token: 7-day TTL, HttpOnly cookie, **single-use** — deleted on use and on logout
- Multi-session: one `RefreshToken` row per session; users list/revoke sessions via `GET/DELETE /api/auth/sessions`. Revoking deletes the row directly (never through the replay-nuke path, which would kill the user's other sessions).
- Password reset deletes **all** of the user's refresh tokens; password change deletes all **except** the session that submitted the change
- No blacklist — short access TTL is the post-logout tolerance window
- Refresh rotation: delete consumed token, issue new pair; replay of a consumed token nukes all the user's refresh tokens

## Login throttling (not account lockout)
Failed logins are throttled per **(email, client IP)** in the `login_throttle` table (`services/auth/login_throttle.py`): 5 free failures, then that pair alone is blocked 1 → 2 → 4 → 8 → 15 min (capped), even for the correct password. The same account from any other address is never blocked. Never reintroduce a per-account lock — it let anyone who knew an email lock its owner out.
- Unknown emails are throttled identically (a 429 must not reveal account existence); the email is stored only as an HMAC.
- Counters reset on success from the pair, on password reset (all pairs), and after 24h quiet; the nightly cleanup deletes stale rows.
- Cross-IP backstop is **alert-only** (`login_account_under_attack` at ≥100 failures/hour), by design.
- The throttle writes through its own session; in tests its writes are stubbed unless the test is marked `@pytest.mark.real_login_throttle`.
- The old `user.failed_login_attempts` / `locked_until` columns are no longer mapped on `User`; the migration that drops them ships one release later (#1186), because the deploy migrates before old tasks stop selecting them.

## Two-factor auth (TOTP, admins)
Admins must have TOTP (#1177): `services/auth/mfa.py` (flows) + `_mfa_codes.py` (code checks, recovery codes), tables `user_mfa`, `mfa_recovery_code`, `mfa_challenge`.
- `get_current_admin` reads `user_mfa` on every request and 403s `mfa_enrollment_required` until enrolment is confirmed. Only the enrolment endpoints use `get_current_admin_pre_mfa`. The token's `mfa` claim is a UI hint only; never enforce on it.
- Login for an MFA user returns `mfa_required` + a 5-minute single-use challenge and **no** token or cookie; `/auth/mfa/verify` issues them. All token issuance for a login goes through `issue_session` (login.py), so `login_success` and the `admin_login` audit mean "got in".
- Confirming enrolment revokes every other session; that is what lets enforcement trust "MFA user ⇒ tokens came through the code step".
- Replay: a code's time-step must be greater than `last_used_step`, claimed atomically. ±1 step skew.
- A bad code counts toward the login throttle for the (email, IP) pair and is audited through its own session (tests point `mfa._session_factory` at the test DB).
- Secrets are Fernet-encrypted with a key derived from `MFA_ENCRYPTION_KEY` (SSM, required in prod). Rotating it forces every user to re-enrol.
- No self-disable. Break-glass is `scripts/reset_mfa.py`: `docs/runbooks/mfa-reset.md`.

## Rate limiting (slowapi)
The `@limiter.limit` decorators in `services/api/rs_api/api/auth/` are the source of truth. Current limits:

| Endpoint | Limit |
|---|---|
| login | 5/minute |
| refresh | 30/minute |
| register (company + candidate) | 3/hour |
| activate · resend-activation · password change · forgot-password | 5/hour |
| reset-password | 10/hour (validate: 30/hour) |
| sessions: list / revoke one / revoke all | 60 / 30 / 10 per minute |
| mfa verify | 10/minute |
| mfa enrol start / confirm | 10/hour |
| mfa recovery-codes | 5/hour |

Never surface the raw slowapi detail string (`"5 per 1 minute"`) in the UI — map to a Hebrew error key.

## Activation flows

**Company:** admin approves invite → activation email → `/activate?token=` → 48h TTL → user activated + company profile linked

Company registration requires a pending, unexpired invite (`validate_invite_token`, then `mark_invite_used` in the same transaction). In tests both endpoints' validation is stubbed (any token is valid) unless the test is marked `@pytest.mark.real_invite_tokens`; build the rows with the `make_invite` fixture.

**Candidate:** `/register-candidate` → activation email (2h TTL) → `/activate?token=` → `CandidateProfile` created + consent (timestamp, policy version, IP, UA) written from the activation request, not the registration request

- Unactivated login (any role): `401 detail=account_pending_activation`
- Login page surfaces "resend activation" affordance for candidates: `POST /api/auth/candidate/resend-activation`

## AuthContext invariant
Resolves initial state synchronously from `localStorage`, then verifies via `/api/auth/me` on mount. Never block render waiting for the verify call — the sync read is the optimistic state.

## What lives where
- Session logic: `libs/shared/rs_shared/services/auth/session.py`
- Registration: `libs/shared/rs_shared/services/auth/registration.py` (company) + `.../candidate_registration.py`
- Activation: `libs/shared/rs_shared/services/auth/activation.py`
- Password reset / change: `libs/shared/rs_shared/services/auth/password_reset.py` + `.../password_change.py`
- MFA: `libs/shared/rs_shared/services/auth/mfa.py`, `_mfa_codes.py`, `mfa_reset.py` (break-glass); router `services/api/rs_api/api/auth/mfa.py`; setup page `frontend/src/pages/admin/MfaSetupPage.tsx`
- Auth API routers: `services/api/rs_api/api/auth/` (incl. `sessions.py` — list/revoke sessions); web infra (auth deps, slowapi limiter): `services/api/rs_api/infrastructure/`
- Route guards: `frontend/src/components/guards/`
