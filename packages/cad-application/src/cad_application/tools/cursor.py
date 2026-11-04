"""Pagination cursors (spec 12.4.2 [Builder's call]).

A cursor is base64url of ``{"o": offset, "t": issue time in ms, "h": hash of the call's other
arguments}``. It is valid for under 10 minutes and only for the same arguments. Cursors are not
secret: a forged offset only selects another page of data the caller may already read.
"""

import base64
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Final, cast

from cad_ir.core.canonical import CanonicalizationError, content_hash
from cad_ir.core.json_types import JsonValue

from cad_application.paths import ToolError
from cad_application.ports import Clock

TTL_MS: Final = 600_000
_MAX_LENGTH: Final = 1024
_MAX_INT: Final = 9_007_199_254_740_991
_ALPHABET: Final = re.compile(r"[A-Za-z0-9_-]*")
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_MS: Final = timedelta(milliseconds=1)


def clock_ms(clock: Clock) -> int:
    """The clock's time in whole milliseconds since the epoch."""
    return (clock.now() - _EPOCH) // _MS


def _digest(args: Mapping[str, JsonValue]) -> str:
    others: dict[str, JsonValue] = {k: v for k, v in args.items() if k != "cursor"}
    return content_hash(others)


def encode_cursor(offset: int, issued_ms: int, args: Mapping[str, JsonValue]) -> str:
    body = {"h": _digest(args), "o": offset, "t": issued_ms}
    raw = json.dumps(body, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _invalid(message: str) -> ToolError:
    issue: JsonValue = {"code": "IR_SCHEMA_INVALID", "pointer": "/cursor", "message": message}
    return ToolError("IR_SCHEMA_INVALID", message, {"issues": [issue]})


def _is_count(value: object) -> bool:
    return type(value) is int and 0 <= value <= _MAX_INT


def _parse(cursor: str) -> tuple[int, int, str] | None:
    if len(cursor) > _MAX_LENGTH or _ALPHABET.fullmatch(cursor) is None:
        return None
    try:
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        body = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    if not isinstance(body, dict):
        return None
    fields = cast("dict[str, object]", body)
    offset, issued, digest = fields.get("o"), fields.get("t"), fields.get("h")
    if isinstance(offset, int) and isinstance(issued, int) and isinstance(digest, str):
        valid = _is_count(offset) and _is_count(issued)
        return (offset, issued, digest) if valid else None
    return None


def decode_cursor(cursor: str, args: Mapping[str, JsonValue], now_ms: int) -> int | ToolError:
    """The offset the cursor stands for, or an ``IR_SCHEMA_INVALID`` error (never raises)."""
    fields = _parse(cursor)
    if fields is None:
        return _invalid("The cursor is malformed.")
    offset, issued, digest = fields
    if issued > now_ms:
        return _invalid("The cursor was issued in the future.")
    if now_ms - issued >= TTL_MS:
        return _invalid("The cursor has expired; repeat the call without a cursor.")
    try:
        same = digest == _digest(args)
    except CanonicalizationError:
        same = False
    if not same:
        return _invalid("The cursor belongs to a call with different arguments.")
    return offset
