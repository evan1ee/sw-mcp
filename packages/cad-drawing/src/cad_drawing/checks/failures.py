"""Failure records shared by the checks (spec 11.5.2 Reporting)."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from cad_ir.core import JsonValue, quantize

from cad_drawing.checks.geometry2d import Vec
from cad_drawing.checks.measure import Measurement

type CheckId = Literal["D1", "D2", "D3", "D7"]

_PAIR = 2


@dataclass(frozen=True, slots=True)
class CheckItem:
    kind: Literal["annotation", "edge", "view"]
    id: str
    index: int | None = None

    def sort_key(self) -> tuple[str, str, int]:
        return (self.kind, self.id, -1 if self.index is None else self.index)

    def to_json(self) -> dict[str, JsonValue]:
        out: dict[str, JsonValue] = {"kind": self.kind, "id": self.id}
        if self.index is not None:
            out["index"] = self.index
        return out


type SortKey = tuple[int, int, tuple[tuple[str, str, int], ...], float, Vec]


@dataclass(frozen=True, slots=True)
class CheckFailure:
    """``items`` are sorted; ``methods`` follows the item order; numbers are quantized."""

    check: CheckId
    sheet: str
    items: tuple[CheckItem, CheckItem] | tuple[CheckItem]
    distance_mm: float
    threshold_mm: float
    location: Vec
    methods: tuple[str | None, ...]

    def sort_key(self, sheet_index: int) -> SortKey:
        return (
            sheet_index,
            int(self.check[1:]),
            tuple(i.sort_key() for i in self.items),
            self.distance_mm,
            self.location,
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "check": self.check,
            "sheet": self.sheet,
            "items": [i.to_json() for i in self.items],
            "distance_mm": self.distance_mm,
            "threshold_mm": self.threshold_mm,
            "location": [self.location[0], self.location[1]],
            "methods": list(self.methods),
        }


def _q(value: float) -> float:
    return float(quantize(value, "length"))


def build_failure(
    check: CheckId,
    sheet: str,
    entries: Sequence[tuple[CheckItem, str | None]],
    measurement: Measurement,
    threshold: float,
) -> CheckFailure:
    """Sort the items (with their read-back methods) and quantize the reported numbers."""
    ordered = sorted(entries, key=lambda e: e[0].sort_key())
    items = tuple(item for item, _ in ordered)
    a, b = measurement.point_a, measurement.point_b
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if len(items) == _PAIR:
        pair: tuple[CheckItem, CheckItem] | tuple[CheckItem] = (items[0], items[1])
    else:
        pair = (items[0],)
    return CheckFailure(
        check=check,
        sheet=sheet,
        items=pair,
        distance_mm=_q(measurement.distance),
        threshold_mm=_q(threshold),
        location=(_q(mid[0]), _q(mid[1])),
        methods=tuple(method for _, method in ordered),
    )


def sort_failures(
    failures: Iterable[CheckFailure], sheet_index: Mapping[str, int]
) -> tuple[CheckFailure, ...]:
    """Order by sheet index, check, then item ids (spec 11.5.2 Reporting)."""
    return tuple(sorted(failures, key=lambda f: f.sort_key(sheet_index[f.sheet])))


type Entries = tuple[tuple[CheckItem, str | None], ...]
type Candidate = tuple[Measurement, Entries, float]


def keep_min(best: dict[tuple[str, ...], Candidate], key: tuple[str, ...], cand: Candidate) -> None:
    """Keep the smallest-distance candidate per key; the first one wins ties."""
    current = best.get(key)
    if current is None or cand[0].distance < current[0].distance:
        best[key] = cand


def emit_failures(
    check: CheckId, sheet: str, best: Mapping[tuple[str, ...], Candidate]
) -> tuple[CheckFailure, ...]:
    """One failure per kept candidate, in key order."""
    return tuple(
        build_failure(check, sheet, entries, m, threshold)
        for _, (m, entries, threshold) in sorted(best.items())
    )
