"""Finite numbers, quanta and deterministic quantization (spec 3.4.3)."""

import math
from decimal import ROUND_HALF_EVEN, Context, Decimal
from typing import Final, Literal

type QuantityKind = Literal["length", "angle", "ratio", "count"]
type LengthUnit = Literal["mm", "in"]

_LENGTH_MM: Final = Decimal("1e-6")
_LENGTH_IN: Final = Decimal("1e-7")
_ANGLE: Final = Decimal("1e-6")
_RATIO: Final = Decimal("1e-9")

# Wide enough that quantizing any finite double (up to ~1.8e308) never signals InvalidOperation.
_WIDE: Final = Context(prec=700, rounding=ROUND_HALF_EVEN)


def quantum(kind: QuantityKind, units: LengthUnit = "mm") -> Decimal:
    """The smallest distinguishable difference for ``kind``. ``count`` has none."""
    if kind == "length":
        return _LENGTH_MM if units == "mm" else _LENGTH_IN
    if kind == "angle":
        return _ANGLE
    if kind == "ratio":
        return _RATIO
    raise ValueError("count has no quantum: counts are compared exactly")


def require_finite(value: object) -> int | float:
    """Return ``value`` if it is a finite int or float. ``bool`` is not a number here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected a finite number, got {type(value).__name__}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"expected a finite number, got {value!r}")
    return value


def quantize(value: int | float, kind: QuantityKind, units: LengthUnit = "mm") -> int | float:
    """Round ``value`` half-even on its decimal repr to the quantum of ``kind``."""
    number = require_finite(value)
    if kind == "count":
        if not isinstance(number, int):
            raise ValueError(f"count must be an int, got {number!r}")
        return number
    q = quantum(kind, units)
    rounded = float(Decimal(repr(float(number))).quantize(q, ROUND_HALF_EVEN, context=_WIDE))
    return 0.0 if rounded == 0.0 else rounded


def values_equal(
    a: int | float, b: int | float, kind: QuantityKind, units: LengthUnit = "mm"
) -> bool:
    """True when ``a`` and ``b`` differ by no more than the quantum of ``kind``."""
    x, y = require_finite(a), require_finite(b)
    if kind == "count":
        return x == y
    return abs(Decimal(repr(x)) - Decimal(repr(y))) <= quantum(kind, units)
