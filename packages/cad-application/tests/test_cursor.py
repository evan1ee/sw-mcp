"""Pagination cursors (spec 12.4.2): same arguments only, valid for under 10 minutes."""

import base64
import json

import pytest
from cad_application.paths import ToolError
from cad_application.tools.cursor import decode_cursor, encode_cursor
from cad_ir.core.canonical import content_hash
from cad_ir.core.json_types import JsonValue

type Args = dict[str, JsonValue]

ARGS: Args = {"report_id": "rep_00000000000000000000000001", "section": "conflicts"}
ISSUED_MS = 1_000_000
TEN_MINUTES_MS = 600_000
OFFSET = 50


def _raw(obj: JsonValue) -> str:
    text = json.dumps(obj).encode("utf-8")
    return base64.urlsafe_b64encode(text).decode("ascii").rstrip("=")


def _is_invalid(result: int | ToolError) -> bool:
    return isinstance(result, ToolError) and result.code == "IR_SCHEMA_INVALID"


def test_cursor_round_trip() -> None:
    cursor = encode_cursor(OFFSET, ISSUED_MS, ARGS)
    assert decode_cursor(cursor, ARGS, ISSUED_MS) == OFFSET


def test_cursor_is_url_safe_text() -> None:
    cursor = encode_cursor(OFFSET, ISSUED_MS, ARGS)
    assert cursor.isascii()
    assert "=" not in cursor
    assert "+" not in cursor
    assert "/" not in cursor


def test_cursor_ignores_the_cursor_argument_itself() -> None:
    first = encode_cursor(OFFSET, ISSUED_MS, ARGS)
    second = encode_cursor(2 * OFFSET, ISSUED_MS, {**ARGS, "cursor": first})
    assert decode_cursor(second, {**ARGS, "cursor": second}, ISSUED_MS) == 2 * OFFSET


@pytest.mark.parametrize(
    "other",
    [
        {**ARGS, "section": "warnings"},
        {**ARGS, "page_size": 10},
        {"report_id": "rep_00000000000000000000000002", "section": "conflicts"},
        {"section": "conflicts"},
        {},
    ],
)
def test_cursor_rejected_for_other_arguments(other: Args) -> None:
    cursor = encode_cursor(OFFSET, ISSUED_MS, ARGS)
    assert _is_invalid(decode_cursor(cursor, other, ISSUED_MS))


def test_cursor_from_another_tool_is_rejected() -> None:
    status_args: Args = {"execution_id": "job_00000000000000000000000001"}
    cursor = encode_cursor(OFFSET, ISSUED_MS, status_args)
    assert _is_invalid(decode_cursor(cursor, ARGS, ISSUED_MS))


def test_cursor_expires_at_ten_minutes() -> None:
    cursor = encode_cursor(OFFSET, ISSUED_MS, ARGS)
    assert decode_cursor(cursor, ARGS, ISSUED_MS + TEN_MINUTES_MS - 1) == OFFSET
    expired = decode_cursor(cursor, ARGS, ISSUED_MS + TEN_MINUTES_MS)
    assert _is_invalid(expired)
    assert isinstance(expired, ToolError)
    assert "expired" in expired.message


def test_cursor_issued_in_the_future_is_rejected() -> None:
    cursor = encode_cursor(OFFSET, ISSUED_MS, ARGS)
    assert _is_invalid(decode_cursor(cursor, ARGS, ISSUED_MS - 1))


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "!!!not base64!!!",
        "ünïcode-cursor",
        "A" * 100_000,
        "\x00",
        base64.urlsafe_b64encode(b"not json").decode("ascii"),
        base64.urlsafe_b64encode(b"\xff\xfe\x00").decode("ascii"),
        base64.urlsafe_b64encode(b"[" * 100_000).decode("ascii"),
        _raw([1, 2, 3]),
        _raw("text"),
        _raw(None),
        _raw({}),
        _raw({"o": 1, "t": 1}),
        _raw({"o": "1", "t": 1, "h": "x"}),
        _raw({"o": True, "t": ISSUED_MS, "h": "x"}),
        _raw({"o": -1, "t": ISSUED_MS, "h": "x"}),
        _raw({"o": 1.5, "t": ISSUED_MS, "h": "x"}),
        _raw({"o": 1, "t": "now", "h": "x"}),
        _raw({"o": 1, "t": ISSUED_MS, "h": 5}),
        _raw({"o": 10**30, "t": ISSUED_MS, "h": "x"}),
    ],
)
def test_cursor_malformed(cursor: str) -> None:
    result = decode_cursor(cursor, ARGS, ISSUED_MS)
    assert _is_invalid(result)
    assert isinstance(result, ToolError)
    assert isinstance(result.details, dict)
    assert "issues" in result.details


def test_cursor_error_does_not_echo_the_cursor() -> None:
    secret = "SECRET-CURSOR-TEXT"
    result = decode_cursor(secret, ARGS, ISSUED_MS)
    assert isinstance(result, ToolError)
    assert secret not in result.message
    assert secret not in json.dumps(result.details)


@pytest.mark.parametrize("offset", [-1, True, 10**30], ids=["negative", "bool", "huge"])
def test_cursor_rejects_bad_offsets_with_valid_hash(offset: JsonValue) -> None:
    digest = content_hash(dict(ARGS))
    cursor = _raw({"h": digest, "o": offset, "t": ISSUED_MS})
    assert _is_invalid(decode_cursor(cursor, ARGS, ISSUED_MS))
