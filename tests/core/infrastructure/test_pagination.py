"""Unit tests for the cursor-pagination helpers."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import Column, DateTime, Integer, String, select
from sqlalchemy.orm import declarative_base

from src.core.infrastructure.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
    decode_cursor,
    encode_cursor,
)
from src.services.exceptions import InvalidCursorError

_Base = declarative_base()


class _PagModel(_Base):
    """Bare ORM model — used only to exercise `apply_cursor`'s query building.

    Never executed against a database; tests inspect the compiled SQL.
    """

    __tablename__ = "_pagination_test_model"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime(timezone=True))


class _Row:
    def __init__(self, row_id: int, created_at: datetime):
        self.id = row_id
        self.created_at = created_at


def test_cursor_round_trip():
    ts = datetime(2026, 5, 7, 12, 34, 56, tzinfo=timezone.utc)
    cursor = encode_cursor(ts, 42)
    assert isinstance(cursor, str)
    assert "=" not in cursor  # padding stripped
    decoded_ts, decoded_secondary, decoded_id = decode_cursor(cursor)
    assert decoded_ts == ts
    assert decoded_secondary is None
    assert decoded_id == 42


def test_decode_cursor_rejects_garbage():
    with pytest.raises(InvalidCursorError):
        decode_cursor("not-a-real-cursor")


def test_decode_cursor_rejects_truncated_payload():
    with pytest.raises(InvalidCursorError):
        decode_cursor(encode_cursor(datetime.now(timezone.utc), 1)[:5])


def test_cursor_round_trip_with_string_value():
    cursor = encode_cursor("Alice", 7, sort_key="name")
    value, secondary, row_id = decode_cursor(cursor, expected_sort_key="name")
    assert value == "Alice"
    assert secondary is None
    assert row_id == 7


def test_decode_cursor_rejects_sort_key_mismatch():
    cursor = encode_cursor("Alice", 7, sort_key="name")
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor, expected_sort_key="created_at")


def test_clamp_limit_defaults_when_none():
    assert clamp_limit(None) == DEFAULT_LIMIT


def test_clamp_limit_floors_below_one():
    assert clamp_limit(0) == 1
    assert clamp_limit(-5) == 1


def test_clamp_limit_caps_at_max():
    assert clamp_limit(MAX_LIMIT + 50) == MAX_LIMIT


def test_clamp_limit_passes_through_valid():
    assert clamp_limit(25) == 25


def _row_key(r: _Row) -> tuple[datetime, int]:
    return r.created_at, r.id


def test_build_cursor_page_no_more_when_under_limit():
    rows = [_Row(1, datetime(2026, 1, 1, tzinfo=timezone.utc))]
    page: CursorPage[int] = build_cursor_page(
        rows,
        serializer=lambda r: r.id,
        cursor_key=_row_key,
        limit=10,
    )
    assert page.items == [1]
    assert page.next_cursor is None


def test_build_cursor_page_emits_cursor_when_more_available():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [_Row(i, base) for i in range(11)]  # limit + 1
    page: CursorPage[int] = build_cursor_page(
        rows,
        serializer=lambda r: r.id,
        cursor_key=_row_key,
        limit=10,
    )
    assert len(page.items) == 10
    assert page.items == list(range(10))
    assert page.next_cursor is not None
    decoded_ts, _decoded_secondary, decoded_id = decode_cursor(page.next_cursor)
    # Boundary points at the last row of the emitted page (id=9).
    assert decoded_id == 9
    assert decoded_ts == base


def test_build_cursor_page_emits_cursor_tagged_with_sort_key():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [_Row(i, base) for i in range(11)]  # limit + 1
    page: CursorPage[int] = build_cursor_page(
        rows,
        serializer=lambda r: r.id,
        cursor_key=_row_key,
        limit=10,
        sort_key="created_at",
    )
    assert page.next_cursor is not None
    # A cursor minted under a different sort_key must be rejected.
    with pytest.raises(InvalidCursorError):
        decode_cursor(page.next_cursor, expected_sort_key="name")
    decoded_value, _decoded_secondary, decoded_id = decode_cursor(
        page.next_cursor, expected_sort_key="created_at"
    )
    assert decoded_id == 9
    assert decoded_value == base


def test_build_cursor_page_supports_tuple_rows():
    """Joined queries return tuples — cursor_key picks the right entity."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class _User:
        def __init__(self, uid: int, ts: datetime):
            self.id = uid
            self.created_at = ts

    rows = [(_User(i, base), object()) for i in range(11)]  # limit + 1
    page: CursorPage[int] = build_cursor_page(
        rows,
        serializer=lambda row: row[0].id,
        cursor_key=lambda row: (row[0].created_at, row[0].id),
        limit=10,
    )
    assert page.next_cursor is not None
    _, _, decoded_id = decode_cursor(page.next_cursor)
    assert decoded_id == 9


def test_apply_cursor_defaults_to_descending_order():
    query = apply_cursor(
        select(_PagModel),
        sort_col=_PagModel.created_at,
        id_col=_PagModel.id,
        cursor=None,
        limit=10,
    )
    compiled = str(query)
    assert "ORDER BY _pagination_test_model.created_at DESC" in compiled
    assert "_pagination_test_model.id DESC" in compiled


def test_apply_cursor_orders_ascending_when_direction_asc():
    query = apply_cursor(
        select(_PagModel),
        sort_col=_PagModel.name,
        id_col=_PagModel.id,
        cursor=None,
        limit=10,
        sort_key="name",
        direction="asc",
    )
    compiled = str(query)
    assert "ORDER BY _pagination_test_model.name ASC" in compiled
    assert "_pagination_test_model.id ASC" in compiled


def test_apply_cursor_rejects_cursor_minted_for_different_sort_key():
    cursor = encode_cursor(datetime.now(timezone.utc), 1, sort_key="created_at")
    with pytest.raises(InvalidCursorError):
        apply_cursor(
            select(_PagModel),
            sort_col=_PagModel.name,
            id_col=_PagModel.id,
            cursor=cursor,
            limit=10,
            sort_key="name",
        )


def test_apply_cursor_accepts_cursor_minted_for_matching_sort_key():
    cursor = encode_cursor("Alice", 1, sort_key="name")
    query = apply_cursor(
        select(_PagModel),
        sort_col=_PagModel.name,
        id_col=_PagModel.id,
        cursor=cursor,
        limit=10,
        sort_key="name",
        direction="asc",
    )
    compiled = str(query)
    assert "_pagination_test_model.name >" in compiled


# ==================== secondary_col (compound sort) ====================


def test_cursor_round_trip_with_secondary_value():
    sort_key = "status,created_at"
    cursor = encode_cursor(1, 7, sort_key=sort_key, secondary_value="2026-01-01")
    value, secondary, row_id = decode_cursor(cursor, expected_sort_key=sort_key)
    assert value == 1
    assert secondary == "2026-01-01"
    assert row_id == 7


def test_apply_cursor_orders_by_secondary_then_id():
    query = apply_cursor(
        select(_PagModel),
        sort_col=_PagModel.id,
        id_col=_PagModel.id,
        cursor=None,
        limit=10,
        secondary_col=_PagModel.created_at,
    )
    compiled = str(query)
    assert (
        "ORDER BY _pagination_test_model.id DESC, "
        "_pagination_test_model.created_at DESC, "
        "_pagination_test_model.id DESC" in compiled
    )


def test_apply_cursor_secondary_direction_independent_of_primary():
    query = apply_cursor(
        select(_PagModel),
        sort_col=_PagModel.id,
        id_col=_PagModel.id,
        cursor=None,
        limit=10,
        direction="asc",
        secondary_col=_PagModel.created_at,
        secondary_direction="desc",
    )
    compiled = str(query)
    assert (
        "ORDER BY _pagination_test_model.id ASC, "
        "_pagination_test_model.created_at DESC, "
        "_pagination_test_model.id DESC" in compiled
    )


def test_apply_cursor_compound_boundary_filters_on_both_columns():
    cursor = encode_cursor(5, 1, secondary_value="x", sort_key="x")
    query = apply_cursor(
        select(_PagModel),
        sort_col=_PagModel.id,
        id_col=_PagModel.id,
        cursor=cursor,
        limit=10,
        sort_key="x",
        secondary_col=_PagModel.name,
    )
    compiled = str(query)
    assert "_pagination_test_model.id <" in compiled
    assert "_pagination_test_model.name <" in compiled


def test_build_cursor_page_emits_compound_cursor():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [_Row(i, base) for i in range(11)]  # limit + 1
    page: CursorPage[int] = build_cursor_page(
        rows,
        serializer=lambda r: r.id,
        cursor_key=lambda r: (r.id, r.created_at, r.id),
        limit=10,
        sort_key="status,created_at",
    )
    assert page.next_cursor is not None
    value, secondary, row_id = decode_cursor(
        page.next_cursor, expected_sort_key="status,created_at"
    )
    assert value == 9
    assert secondary == base
    assert row_id == 9
