"""Dependency-inversion boundary for candidate account provisioning.

The public apply flow can, on an anonymous "claim" (password supplied),
provision a candidate ``User`` + activation token. That behavior is owned by the
``auth`` domain (``register_candidate``), but the apply flow lives in ``public``.
Rather than ``public`` importing ``auth`` (a cross-domain edge, and historically
a circular-import hazard), the flow depends on this ``Protocol`` and the
composition root (``rs_api``) injects the concrete ``auth`` implementation.

``register_candidate``'s signature satisfies this protocol directly, so no
adapter is needed at the injection site.
"""

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class CandidateProvisioner(Protocol):
    """Creates a (pending) candidate account for a claimed application."""

    async def __call__(
        self,
        email: str,
        password: str,
        full_name: str,
        *,
        privacy_accepted: bool,
        terms_accepted: bool,
        session: AsyncSession,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None: ...
