"""Semantic groupings on the shared enums.

These guard the single source of truth that consumers derive from
(``is_active`` / ``is_terminal`` / ``company_visible`` / ``company_settable`` /
``sort_weight``) so a future value can't silently fall out of a grouping.
"""

from rs_shared.enums import ACTIVE_APPLICATION_STATUSES
from rs_shared.enums import ApplicationStatus as S


def test_rejected_is_split_by_actor():
    """The overloaded ``REJECTED`` value is gone, replaced by the actor split."""
    assert not hasattr(S, "REJECTED")
    assert S.REJECTED_BY_ADMIN in S
    assert S.REJECTED_BY_COMPANY in S


def test_active_and_terminal_partition_the_enum():
    active = {s for s in S if s.is_active}
    terminal = {s for s in S if s.is_terminal}
    assert active.isdisjoint(terminal)
    assert active | terminal == set(S)


def test_active_statuses():
    assert {s for s in S if s.is_active} == {
        S.PENDING_ADMIN_REVIEW,
        S.APPROVED_BY_ADMIN,
        S.INTERVIEWING,
        S.OFFER,
    }


def test_active_application_statuses_tracks_is_active():
    """The query-ready tuple must not drift from the ``is_active`` property.

    Consumers put this straight into SQL ``IN`` clauses (the close cascade, the
    retention purge), so a value falling out of sync here would silently change
    who gets swept and who gets purged.
    """
    assert set(ACTIVE_APPLICATION_STATUSES) == {s for s in S if s.is_active}
    # Ordered by the pipeline, so generated SQL is stable across runs.
    assert list(ACTIVE_APPLICATION_STATUSES) == sorted(
        ACTIVE_APPLICATION_STATUSES, key=lambda s: s.sort_weight
    )


def test_company_settable_is_a_subset_of_company_visible():
    settable = {s for s in S if s.company_settable}
    visible = {s for s in S if s.company_visible}
    assert settable <= visible


def test_company_never_sees_admin_screen_outs():
    """An RS screen-out happens before the employer is involved."""
    assert not S.REJECTED_BY_ADMIN.company_visible
    assert not S.REJECTED_BY_ADMIN.company_settable


def test_company_settable_statuses():
    assert {s for s in S if s.company_settable} == {
        S.INTERVIEWING,
        S.OFFER,
        S.HIRED,
        S.REJECTED_BY_COMPANY,
    }


def test_sort_weight_is_a_stable_total_order():
    weights = [s.sort_weight for s in S]
    assert sorted(weights) == list(range(len(list(S))))
    # Pipeline order: intake precedes decisions precedes withdrawals/closures.
    assert S.PENDING_ADMIN_REVIEW.sort_weight < S.APPROVED_BY_ADMIN.sort_weight
    assert S.APPROVED_BY_ADMIN.sort_weight < S.HIRED.sort_weight
    assert S.HIRED.sort_weight < S.JOB_CLOSED.sort_weight
