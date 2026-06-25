"""Cursor-based pagination helpers for admin list endpoints.

Forward-only keyset pagination, default on `(created_at desc, id desc)`. The
cursor is an opaque base64-encoded JSON object describing the boundary row's
sort value(s) and id; the next page contains rows strictly past that
boundary. An optional secondary column supports compound sorts (e.g. "status,
then date").
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from typing import Any, Callable, Generic, Literal, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import InstrumentedAttribute

from src.services.exceptions import InvalidCursorError

M = TypeVar("M")
R = TypeVar("R")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

SortValue = datetime | str | int
Direction = Literal["asc", "desc"]
CursorKey = tuple[SortValue, int] | tuple[SortValue, SortValue | None, int]

_DATETIME_TAG = "d"
_STRING_TAG = "s"
_INT_TAG = "n"


class CursorPage(BaseModel, Generic[M]):
    """A single page of items with an opaque cursor for the next page."""

    items: list[M]
    next_cursor: str | None = None


def _serialize_value(value: SortValue) -> dict[str, Any]:
    if isinstance(value, datetime):
        return {"t": _DATETIME_TAG, "v": value.isoformat()}
    if isinstance(value, bool):  # bool is an int subclass — check first
        return {"t": _STRING_TAG, "v": str(value)}
    if isinstance(value, int):
        return {"t": _INT_TAG, "v": value}
    return {"t": _STRING_TAG, "v": value}


def _deserialize_value(payload: dict[str, Any]) -> SortValue:
    tag, raw = payload["t"], payload["v"]
    if tag == _DATETIME_TAG:
        return datetime.fromisoformat(raw)
    if tag == _INT_TAG:
        return int(raw)
    return str(raw)


def encode_cursor(
    value: SortValue,
    row_id: int,
    *,
    sort_key: str = "created_at",
    secondary_value: SortValue | None = None,
) -> str:
    """Encode the boundary row's sort value(s) and id as an opaque cursor.

    `sort_key` identifies which column(s) `value`/`secondary_value` came
    from, so `decode_cursor` can reject a cursor minted under a different
    sort (e.g. the client changed `sort` without dropping the cursor).
    """
    payload: dict[str, Any] = {
        "k": sort_key,
        "v": _serialize_value(value),
        "id": row_id,
    }
    if secondary_value is not None:
        payload["v2"] = _serialize_value(secondary_value)
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(
    cursor: str, *, expected_sort_key: str = "created_at"
) -> tuple[SortValue, SortValue | None, int]:
    """Decode a cursor back to `(value, secondary_value, id)`.

    Raises:
        InvalidCursorError: If the cursor is malformed, unparseable, or was
            minted under a different sort than `expected_sort_key` (e.g. the
            client changed `sort` without dropping the cursor).
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if payload["k"] != expected_sort_key:
            raise ValueError("cursor sort key mismatch")
        value = _deserialize_value(payload["v"])
        secondary_value = _deserialize_value(payload["v2"]) if "v2" in payload else None
        return value, secondary_value, int(payload["id"])
    except (
        binascii.Error,
        UnicodeDecodeError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise InvalidCursorError("Invalid pagination cursor") from exc


def clamp_limit(limit: int | None) -> int:
    """Clamp the user-supplied `limit` to `[1, MAX_LIMIT]`; default `DEFAULT_LIMIT`."""
    if limit is None:
        return DEFAULT_LIMIT
    if limit < 1:
        return 1
    if limit > MAX_LIMIT:
        return MAX_LIMIT
    return limit


def apply_cursor(
    query: Select[Any],
    *,
    sort_col: InstrumentedAttribute[Any],
    id_col: InstrumentedAttribute[Any],
    cursor: str | None,
    limit: int,
    sort_key: str = "created_at",
    direction: Direction = "desc",
    secondary_col: InstrumentedAttribute[Any] | None = None,
    secondary_direction: Direction | None = None,
) -> Select[Any]:
    """Add keyset filter, order, and `limit + 1` to a select.

    Sorted by `sort_col` (then `secondary_col`, if given) then `id_col`, each
    in its own direction (`secondary_direction` defaults to `direction`).
    When `cursor` is set, only rows strictly past the boundary row are
    returned. Selecting one extra row lets the caller detect whether another
    page exists. `sort_key` identifies the active sort for the cursor — see
    `decode_cursor`.
    """
    sec_direction: Direction = secondary_direction or direction
    if cursor is not None:
        boundary_val, boundary_sec, boundary_id = decode_cursor(
            cursor, expected_sort_key=sort_key
        )
        primary_cmp = (
            sort_col < boundary_val if direction == "desc" else sort_col > boundary_val
        )
        primary_eq = sort_col == boundary_val
        if secondary_col is not None:
            sec_cmp = (
                secondary_col < boundary_sec
                if sec_direction == "desc"
                else secondary_col > boundary_sec
            )
            sec_eq = secondary_col == boundary_sec
            id_cmp = (
                id_col < boundary_id
                if sec_direction == "desc"
                else id_col > boundary_id
            )
            query = query.where(
                or_(
                    primary_cmp,
                    and_(primary_eq, sec_cmp),
                    and_(primary_eq, sec_eq, id_cmp),
                )
            )
        else:
            id_cmp = (
                id_col < boundary_id if direction == "desc" else id_col > boundary_id
            )
            query = query.where(or_(primary_cmp, and_(primary_eq, id_cmp)))

    order_cols = [sort_col.asc() if direction == "asc" else sort_col.desc()]
    if secondary_col is not None:
        order_cols.append(
            secondary_col.asc() if sec_direction == "asc" else secondary_col.desc()
        )
        order_cols.append(id_col.asc() if sec_direction == "asc" else id_col.desc())
    else:
        order_cols.append(id_col.asc() if direction == "asc" else id_col.desc())
    return query.order_by(*order_cols).limit(limit + 1)


def build_cursor_page(
    rows: list[R],
    *,
    serializer: Callable[[R], M],
    cursor_key: Callable[[R], CursorKey],
    limit: int,
    sort_key: str = "created_at",
) -> CursorPage[M]:
    """Slice up to `limit` rows from a `limit+1` fetch and emit the next cursor.

    `cursor_key(row)` returns either `(value, id)`, or for a compound sort
    `(value, secondary_value, id)` — the key(s) that should encode the
    boundary for the active `sort_key`. Using a callable lets joined/tuple
    result sets pull the key from a specific entity instead of relying on
    attr names.
    """
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor: str | None = None
    if has_more and page_rows:
        key = cursor_key(page_rows[-1])
        if len(key) == 3:
            value, secondary_value, row_id = key
        else:
            value, row_id = key
            secondary_value = None
        next_cursor = encode_cursor(
            value, row_id, sort_key=sort_key, secondary_value=secondary_value
        )
    return CursorPage(
        items=[serializer(r) for r in page_rows],
        next_cursor=next_cursor,
    )
