import math
from decimal import Decimal

import pytest
from cad_ir.core.numbers import (
    LengthUnit,
    QuantityKind,
    quantize,
    quantum,
    require_finite,
    values_equal,
)


@pytest.mark.parametrize(
    ("value", "kind", "units", "expected"),
    [
        (0.1 + 0.2, "length", "mm", 0.3),
        (1.0000005, "length", "mm", 1.0),
        (1.0000015, "length", "mm", 1.000002),
        (1.00000004, "length", "in", 1.0),
        (0.1234567891, "ratio", "mm", 0.123456789),
        (90.0000004, "angle", "mm", 90.0),
        (1e300, "length", "mm", 1e300),
        (3, "count", "mm", 3),
    ],
)
def test_quantize(value: float, kind: QuantityKind, units: LengthUnit, expected: float) -> None:
    assert quantize(value, kind, units) == expected


def test_quantize_half_even_and_negative_zero() -> None:
    r = quantize(-0.0000001, "length")
    assert r == 0.0
    assert math.copysign(1, r) == 1


def test_quantize_count_must_be_int() -> None:
    with pytest.raises(ValueError, match="count"):
        quantize(2.5, "count")
    with pytest.raises(ValueError, match="count"):
        quantize(2.0, "count")
    with pytest.raises(ValueError, match="finite number"):
        quantize(True, "count")


def test_quantize_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="finite"):
        quantize(math.nan, "length")


def test_quantum_values() -> None:
    assert quantum("length") == Decimal("1e-6")
    assert quantum("length", "in") == Decimal("1e-7")
    assert quantum("angle") == Decimal("1e-6")
    assert quantum("ratio") == Decimal("1e-9")
    with pytest.raises(ValueError, match="count"):
        quantum("count")


def test_values_equal_quanta() -> None:
    assert values_equal(10.0, 10.000001, "length")
    assert not values_equal(10.0, 10.0000011, "length")
    assert values_equal(1.0, 1.0000001, "length", "in")
    assert not values_equal(1.0, 1.0000002, "length", "in")
    assert values_equal(90.0, 90.000001, "angle")
    assert not values_equal(3, 4, "count")
    assert values_equal(4, 4, "count")


@pytest.mark.parametrize("v", [math.nan, math.inf, -math.inf, True, False, "1.0", None, [1]])
def test_require_finite_rejects(v: object) -> None:
    with pytest.raises(ValueError, match=r"finite number"):
        require_finite(v)


@pytest.mark.parametrize("v", [0, 1, -2.5, 1e300])
def test_require_finite_accepts(v: float) -> None:
    assert require_finite(v) == v
