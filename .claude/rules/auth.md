# Auth Rules

## Token model
- Access token: 10min TTL, stored in `localStorage`
- Refresh token: 1-day TTL (30 days with "remember me"), HttpOnly cookie, **single-use** — deleted on use and on logout
- Multi-session: one `RefreshToken` row per session; users list/revoke sessions via `GET/DELETE /api/auth/sessions`. Revoking deletes the row directly (never through the replay-nuke path, which would kill the user's other sessions).
- Password reset deletes **all** of the user's refresh tokens; password change deletes all **except** the session that submitted the change. Both also clear the MFA code lock and delete pending MFA login challenges.
- No blacklist — short access TTL is the post-logout tolerance window
- Refresh rotation: delete consumed token, issue new pair; replay of a consumed token nukes all the user's refresh tokens

## Login throttling (not account lockout)
Failed logins are throttled per **(email, client IP)** in the `login_throttle` table (`services/auth/login_throttle.py`): 5 free failures, then that pair alone is blocked 1 → 2 → 4 → 8 → 15 min (capped), even for the correct password. The same account from any other address is never blocked. Never reintroduce a per-account lock — it let anyone who knew an email lock its owner out.
- Unknown emails are throttled identically (a 429 must not reveal account existence); the email is stored only as an HMAC.
- Counters reset on success from the pair, on password reset (all pairs), and after 24h quiet; the nightly cleanup deletes stale rows.
- Cross-IP backstop is **alert-only** (`login_account_under_attack` at ≥100 failures/hour), by design.
- The throttle writes through its own session; in tests its writes are stubbed unless the test is marked `@pytest.mark.real_login_throttle`.

## Audit rows
Every login writes `user.login`; a wrong password on a real account writes `user.login_failed` inside the throttle's own transaction (stubbed with it in tests); refresh-token replay writes `user.session_replay` inside the nuke's session; a wrong MFA code writes `mfa_verify_failed` inside the lock count's session. Those own-session rows use `record_audit_event_best_effort` (a SAVEPOINT): an audit failure must never undo the nuke or the throttle count. Unknown emails get no row, and no row ever holds an email.
- The old `user.failed_login_attempts` / `locked_until` columns are no longer mapped on `User`; the migration that drops them ships one release later (#1186), because the deploy migrates before old tasks stop selecting them.

## Two-factor auth (TOTP, admins)
Admins must have TOTP (#1177): `services/auth/mfa.py` (enrolment, status), `mfa_challenge.py` (the login code step), `_mfa_codes.py` (code checks, recovery codes), `_mfa_lockout.py` (per-account lock), `_mfa_notify.py` (owner emails); tables `user_mfa`, `mfa_recovery_code`, `mfa_challenge`, plus `refreshtoken.mfa_verified`.
- **Two checks, both from the DB, never a token claim.** `get_current_user` refuses (401 `session_revoked`) any session of an MFA user whose refresh row isn't `mfa_verified`, and `refresh_user_tokens` won't rotate one. `get_current_admin` 403s `mfa_enrollment_required` until enrolment is confirmed; only the enrolment endpoints use `get_current_admin_pre_mfa`. The JWT `mfa` claim mirrors the session flag for the SPA's routing only.
- Only the code step (`issue_session(..., mfa_verified=True)` from `/auth/mfa/verify`) and the enrolment (its own session) set `mfa_verified`; rotation carries it. Login for an MFA user returns `mfa_required` + a 5-minute challenge and **no** token or cookie. All login token issuance goes through `issue_session`, so `login_success` and the `user.login` audit mean "got in".
- Confirming enrolment revokes every other session.
- Challenge attempts are reserved with one conditional UPDATE in their own session *before* the code is checked (cap 5, no concurrent overrun); success consumes the challenge with a conditional DELETE (two right answers can't both log in).
- Replay: a code's time-step must be greater than `last_used_step`, claimed atomically. ±1 step skew.
- A wrong code counts per account (5 free, then the code step is locked 5 → 10 → 20 → 40 → 60 min, cleared only by a right code, a password reset/change or the break-glass reset) and per (email, IP) in the login throttle. That includes the code for regenerating recovery codes. The wrong code that locks answers 429 `mfa_locked` at once; lock 429s carry `Retry-After` (seconds), which the SPA shows as minutes. The time-step claim re-checks the lock, so a burst can't race past it. A new challenge replaces the user's earlier one. The per-IP throttle alone isn't enough: a correct password clears its pair. Writes go through their own sessions (tests point `mfa_challenge._session_factory` and `_mfa_lockout._session_factory` at the test DB).
- The owner is emailed on enrolment, recovery-code use (with codes left), regeneration, the first lock of a run, and a break-glass reset.
- Secrets are Fernet-encrypted and recovery codes HMAC-hashed, with per-purpose keys derived from `MFA_ENCRYPTION_KEY` (SSM, required in prod, not in the DB). Rotating it forces every user to re-enrol.
- MFA responses and token-issuing responses are `Cache-Control: no-store`.
- No self-disable. Break-glass is `scripts/reset_mfa.py --operator … --reason …`: `docs/runbooks/mfa-reset.md`.
- The nightly cleanup deletes expired challenges and enrolments left unconfirmed for 7 days (`purge_stale_mfa_rows`).

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
| mfa status | 60/minute |

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
- MFA: `libs/shared/rs_shared/services/auth/mfa.py`, `mfa_challenge.py`, `_mfa_codes.py`, `_mfa_lockout.py`, `_mfa_notify.py`, `mfa_reset.py` (break-glass); router `services/api/rs_api/api/auth/mfa.py`; setup page `frontend/src/pages/admin/MfaSetupPage.tsx`
- Auth API routers: `services/api/rs_api/api/auth/` (incl. `sessions.py` — list/revoke sessions); web infra (auth deps, slowapi limiter): `services/api/rs_api/infrastructure/`
- Route guards: `frontend/src/components/guards/`
