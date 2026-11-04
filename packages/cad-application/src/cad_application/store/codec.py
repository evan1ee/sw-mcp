"""JSON encoding, decoding with schema validation, timestamps and typed field access."""

import json
from datetime import UTC, datetime
from typing import Final

from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema

from cad_application.store.errors import StoreError, corrupt

STORE_SCHEMA: Final = "https://sw-mcp.invalid/schemas/store/v0.json"
_TS_FORMAT: Final = "%Y-%m-%dT%H:%M:%S.%fZ"
_MS_PER_US: Final = 1000

type Obj = dict[str, JsonValue]


def format_ts(moment: datetime) -> str:
    """UTC ISO 8601 with milliseconds (13.2.1)."""
    utc = moment.astimezone(UTC)
    return f"{utc:%Y-%m-%dT%H:%M:%S}.{utc.microsecond // _MS_PER_US:03d}Z"


def parse_ts(text: str) -> datetime:
    return datetime.strptime(text, _TS_FORMAT).replace(tzinfo=UTC)


def encode(value: JsonValue) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def encode_line(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def decode_json(data: bytes, file: str) -> JsonValue | StoreError:
    """Parse JSON; failures name the file and the reason, never the content."""
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):  # too deep to decode is corrupt
        return corrupt("unreadable", file)


def decode_record(data: bytes, def_name: str, file: str) -> Obj | StoreError:
    """Parse JSON and validate it against ``#/$defs/<def_name>`` of the store schema."""
    value = decode_json(data, file)
    if isinstance(value, StoreError):
        return value
    try:
        issues = validate_against_schema(value, f"{STORE_SCHEMA}#/$defs/{def_name}")
    except RecursionError:
        return corrupt("unreadable", file)
    if issues:
        return corrupt("schema", file)
    if not isinstance(value, dict):
        return corrupt("schema", file)
    return value


# Accessors for values already validated against the schema.


def get_str(obj: Obj, key: str) -> str:
    value = obj[key]
    if not isinstance(value, str):
        raise TypeError(key)
    return value


def get_opt_str(obj: Obj, key: str) -> str | None:
    value = obj.get(key)
    if value is not None and not isinstance(value, str):
        raise TypeError(key)
    return value


def get_bool(obj: Obj, key: str) -> bool:
    value = obj[key]
    if not isinstance(value, bool):
        raise TypeError(key)
    return value


def get_int(obj: Obj, key: str) -> int:
    value = obj[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(key)
    return value


def get_list(obj: Obj, key: str) -> list[JsonValue]:
    value = obj[key]
    if not isinstance(value, list):
        raise TypeError(key)
    return value


def get_obj(obj: Obj, key: str) -> Obj:
    value = obj[key]
    if not isinstance(value, dict):
        raise TypeError(key)
    return value


def as_obj(value: JsonValue) -> Obj:
    if not isinstance(value, dict):
        raise TypeError("object expected")
    return value
