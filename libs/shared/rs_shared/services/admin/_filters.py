"""Shared query predicates for the admin list endpoints."""

from sqlalchemy import ColumnElement

from rs_shared.models import CandidateProfile


def candidate_not_deleted() -> ColumnElement[bool]:
    """Match candidate profiles that have not been tombstoned.

    Both the candidates list and the applications list hide tombstoned
    candidates by default, and each has a separate ``sort="score"`` path that
    builds its own statement — four call sites for one rule. Kept here so the
    definition of "deleted" (and its pyright suppression) lives in one place.
    """
    return CandidateProfile.deleted_at.is_(None)  # pyright: ignore[reportArgumentType]
