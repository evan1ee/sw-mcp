"""Canonical form and content hashes (spec 3.4.4)."""

import hashlib
from collections.abc import Callable

import rfc8785

from cad_ir.core.json_types import JsonValue
from cad_ir.core.numbers import LengthUnit, QuantityKind, quantize
from cad_ir.core.pointer import escape_token

type QuantityLookup = Callable[[str], tuple[QuantityKind, LengthUnit] | None]
type UnorderedLookup = Callable[[str], bool]


class CanonicalizationError(ValueError):
    """A value cannot be put in RFC 8785 form (non-finite number, unsafe integer, bad type)."""


def canonical_bytes(value: JsonValue) -> bytes:
    """Serialize ``value`` with RFC 8785 (JSON Canonicalization Scheme)."""
    try:
        return rfc8785.dumps(value)
    except rfc8785.CanonicalizationError as e:
        raise CanonicalizationError(str(e)) from e


def content_hash(value: JsonValue) -> str:
    """``sha256:`` plus the lowercase hex SHA-256 of the canonical serialization."""
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _no_quantity(_pointer: str) -> tuple[QuantityKind, LengthUnit] | None:
    return None


def _never_unordered(_pointer: str) -> bool:
    return False


def canonicalize(
    value: JsonValue,
    *,
    quantity_at: QuantityLookup = _no_quantity,
    unordered_at: UnorderedLookup = _never_unordered,
) -> JsonValue:
    """Return a canonicalized copy: numbers quantized and unordered arrays sorted.

    The callbacks receive the JSON Pointer of each node. The input is never mutated.
    """
    return _walk(value, "", quantity_at, unordered_at)


def _walk(
    value: JsonValue, pointer: str, quantity_at: QuantityLookup, unordered_at: UnorderedLookup
) -> JsonValue:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        quantity = quantity_at(pointer)
        return value if quantity is None else quantize(value, quantity[0], quantity[1])
    if isinstance(value, dict):
        return {
            k: _walk(v, f"{pointer}/{escape_token(k)}", quantity_at, unordered_at)
            for k, v in value.items()
        }
    items = [_walk(v, f"{pointer}/{i}", quantity_at, unordered_at) for i, v in enumerate(value)]
    if unordered_at(pointer):
        items.sort(key=canonical_bytes)
    return items
