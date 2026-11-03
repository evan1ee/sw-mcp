"""Runs the geometry checks in a fixed order (spec 11.5.2)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from cad_ir.core import JsonValue

from cad_drawing.checks.d1 import check_d1
from cad_drawing.checks.d2 import check_d2
from cad_drawing.checks.d3 import check_d3
from cad_drawing.checks.d7 import check_d7
from cad_drawing.checks.failures import CheckFailure, sort_failures
from cad_drawing.checks.primitives import Prim, sheet_primitives
from cad_drawing.checks.snapshot import Sheet, Snapshot
from cad_drawing.checks.soft_metrics import SoftMetrics, compute_soft_metrics
from cad_drawing.checks.thresholds import CheckThresholds

CHECK_IDS: tuple[str, ...] = ("D1", "D2", "D3", "D7")

type CheckFn = Callable[[Sheet, Sequence[Prim], CheckThresholds], tuple[CheckFailure, ...]]

_CHECKS: tuple[CheckFn, ...] = (check_d1, check_d2, check_d3, check_d7)


@dataclass(frozen=True, slots=True)
class GeometryCheckResult:
    thresholds: CheckThresholds
    failures: tuple[CheckFailure, ...]
    soft_metrics: Mapping[str, SoftMetrics]
    sheet_indexes: Mapping[str, int]
    evaluated: tuple[str, ...] = CHECK_IDS

    def status(self, check: str) -> Literal["pass", "fail", "not_evaluated"]:
        if check not in self.evaluated:
            return "not_evaluated"
        return "fail" if any(f.check == check for f in self.failures) else "pass"

    def to_json(self) -> JsonValue:
        """Keyed by sheet, then check; failures keep their sorted order."""
        sheets: dict[str, JsonValue] = {}
        for key, metrics in sorted(self.soft_metrics.items()):
            entry: dict[str, JsonValue] = {"index": self.sheet_indexes[key]}
            for check in self.evaluated:
                found: list[JsonValue] = [
                    f.to_json() for f in self.failures if f.sheet == key and f.check == check
                ]
                entry[check] = {"status": "fail" if found else "pass", "failures": found}
            entry["soft_metrics"] = metrics.to_json()
            sheets[key] = entry
        return {
            "thresholds": self.thresholds.to_json(),
            "evaluated": list(self.evaluated),
            "sheets": sheets,
        }


def run_geometry_checks(
    snapshot: Snapshot, t: CheckThresholds | None = None
) -> GeometryCheckResult:
    """D1, D2, D3 and D7 plus soft metrics on every sheet; prims are built once per sheet."""
    thresholds = t or CheckThresholds()
    failures: list[CheckFailure] = []
    metrics: dict[str, SoftMetrics] = {}
    for sheet in snapshot.sheets:
        prims = sheet_primitives(sheet, thresholds)
        for check in _CHECKS:
            failures.extend(check(sheet, prims, thresholds))
        metrics[sheet.key] = compute_soft_metrics(sheet, prims, thresholds)
    order = {s.key: s.index for s in snapshot.sheets}
    return GeometryCheckResult(thresholds, sort_failures(failures, order), metrics, order)
