import hashlib
import math

import pytest
from cad_ir.core.canonical import (
    CanonicalizationError,
    canonical_bytes,
    canonicalize,
    content_hash,
)
from cad_ir.core.json_types import JsonValue
from cad_ir.core.numbers import LengthUnit, QuantityKind


def test_canonical_bytes_rfc8785() -> None:
    assert canonical_bytes({"b": 1, "a": [1.0, "x"]}) == b'{"a":[1,"x"],"b":1}'
    assert canonical_bytes([1e21, 1e-7, -0.0]) == b"[1e+21,1e-7,0]"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 2**60])
def test_canonical_bytes_rejects_unrepresentable(bad: float) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_bytes({"x": bad})


def test_content_hash() -> None:
    assert content_hash({}) == "sha256:" + hashlib.sha256(b"{}").hexdigest()


def test_canonicalize_quantizes_and_sorts_without_mutation() -> None:
    raw = 0.1000004
    doc: dict[str, JsonValue] = {"covers": ["b", "a"], "x": raw, "seq": [2, 1], "flag": True}

    def quantity_at(p: str) -> tuple[QuantityKind, LengthUnit] | None:
        return ("length", "mm") if p == "/x" else None

    out = canonicalize(doc, quantity_at=quantity_at, unordered_at=lambda p: p == "/covers")
    assert out == {"covers": ["a", "b"], "x": 0.1, "seq": [2, 1], "flag": True}
    assert doc == {"covers": ["b", "a"], "x": raw, "seq": [2, 1], "flag": True}


def test_canonicalize_bool_is_not_a_number() -> None:
    out = canonicalize({"flag": True}, quantity_at=lambda _p: ("count", "mm"))
    assert out == {"flag": True}


def test_canonicalize_pointers_escape_and_nest() -> None:
    seen: list[str] = []

    def quantity_at(p: str) -> tuple[QuantityKind, LengthUnit] | None:
        seen.append(p)
        return None

    canonicalize({"a/b": [{"m~n": 1}]}, quantity_at=quantity_at)
    assert seen == ["/a~1b/0/m~0n"]


def test_canonicalize_sorts_nested_unordered_by_canonical_bytes() -> None:
    out = canonicalize({"s": [{"b": 1}, {"a": 2}, 3]}, unordered_at=lambda p: p == "/s")
    assert out == {"s": [3, {"a": 2}, {"b": 1}]}
