"""Failure records, ordering and measuring (plan Task 4)."""

from typing import Literal, cast

import pytest
from cad_drawing.checks.failures import (
    CheckFailure,
    CheckId,
    CheckItem,
    build_failure,
    sort_failures,
)
from cad_drawing.checks.geometry2d import Segment
from cad_drawing.checks.measure import Measurement, measure
from cad_drawing.checks.primitives import Prim

QUANTIZED = 0.123457
GAP = 3.0


def failure(check: Literal["D1", "D2"], sheet: str, a: str, b: str) -> CheckFailure:
    return build_failure(
        check,
        sheet,
        [(CheckItem("annotation", a), None), (CheckItem("annotation", b), None)],
        Measurement(0.0, (0.0, 0.0), (0.0, 0.0)),
        0.01,
    )


def test_build_failure_sorts_items_and_methods_and_quantizes() -> None:
    f = build_failure(
        "D3",
        "s_0",
        [(CheckItem("edge", "v_a", 3), None), (CheckItem("annotation", "n1"), "font_metrics")],
        Measurement(0.123456789, (1.0000001, 2.0), (3.0, 2.0)),
        0.25,
    )
    assert f.items == (CheckItem("annotation", "n1"), CheckItem("edge", "v_a", 3))
    assert f.methods == ("font_metrics", None)
    assert f.distance_mm == QUANTIZED
    assert f.location == (2.0, 2.0)
    assert f.to_json() == {
        "check": "D3",
        "sheet": "s_0",
        "items": [{"kind": "annotation", "id": "n1"}, {"kind": "edge", "id": "v_a", "index": 3}],
        "distance_mm": QUANTIZED,
        "threshold_mm": 0.25,
        "location": [2.0, 2.0],
        "methods": ["font_metrics", None],
    }


def test_single_item_failure() -> None:
    f = build_failure(
        "D7",
        "s_0",
        [(CheckItem("view", "v1"), None)],
        Measurement(1.5, (1.0, 1.0), (1.0, 1.0)),
        0.01,
    )
    assert f.items == (CheckItem("view", "v1"),)
    assert f.methods == (None,)


def test_sort_failures_by_sheet_index_then_check_then_items() -> None:
    f1 = failure("D2", "s_b", "a", "b")
    f2 = failure("D1", "s_b", "a", "c")
    f3 = failure("D1", "s_b", "a", "b")
    f4 = failure("D1", "s_a", "z", "y")
    assert sort_failures([f1, f2, f3, f4], {"s_a": 1, "s_b": 0}) == (f3, f2, f1, f4)


def test_measure_segments_and_containment() -> None:
    a = Prim("dimension_line", "a", (Segment((0, 0), (10, 0)),), None, None, None, 0)
    b = Prim("dimension_line", "b", (Segment((0, 3), (10, 3)),), None, None, None, 0)
    m = measure(a, b)
    assert m is not None
    assert m.distance == GAP
    big = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    inner = ((4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0))
    inside = measure(
        Prim("text_box", "o", (), big, None, None, 0),
        Prim("text_box", "i", (), inner, None, None, 0),
    )
    assert inside is not None
    assert inside.distance == 0.0
    point = Prim("text_box", "p", (), ((1.0, 1.0),) * 4, None, None, 0)
    far = measure(point, Prim("edge", "e", (Segment((4, 1), (9, 1)),), None, None, None, 0))
    assert far is not None
    assert far.distance == pytest.approx(GAP, abs=1e-12)


def test_measure_empty_is_none() -> None:
    empty = Prim("edge", "e", (), None, None, None, 0)
    assert measure(empty, empty) is None


def test_sort_failures_orders_check_ids_by_their_number() -> None:
    early = failure("D2", "s_a", "a", "b")
    late = build_failure(
        cast(CheckId, "D10"),
        "s_a",
        [(CheckItem("annotation", "a"), None), (CheckItem("annotation", "b"), None)],
        Measurement(0.0, (0.0, 0.0), (0.0, 0.0)),
        0.01,
    )
    assert sort_failures([late, early], {"s_a": 0}) == (early, late)
