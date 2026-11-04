"""The drawing report: all checks D1-D10 in one derived artifact (spec 11.5.4).

A pure function of the snapshot, the thresholds and the title-block mappings: no clock reading,
no store IDs. D4, D6 and D9 need a Drawing Intent, so a Phase 1a report is never ``done``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from cad_ir.core import (
    CanonicalizationError,
    IssueReport,
    JsonValue,
    ValidationIssue,
    content_hash,
)
from cad_ir.core import build_report as build_issue_report
from cad_ir.generated import ErrorCode

from cad_drawing.checks.d5 import check_d5
from cad_drawing.checks.d8 import TitleBlockMapping, check_d8
from cad_drawing.checks.d10 import check_d10
from cad_drawing.checks.outcome import CheckOutcome, CheckStatus, CheckWarning, RuleFailure
from cad_drawing.checks.runner import GeometryCheckResult, run_geometry_checks
from cad_drawing.checks.snapshot import Snapshot, parse_snapshot
from cad_drawing.checks.thresholds import CheckThresholds

REPORT_SCHEMA_ID: Final = "https://sw-mcp.invalid/schemas/drawing-report/v0.json"
REPORT_SCHEMA_VERSION: Final = "0.1"
CALIBRATION_NOTE: Final = (
    "Checks have run only on synthetic snapshots; results are unverified on real SOLIDWORKS data."
)
ALL_CHECKS: Final[tuple[str, ...]] = tuple(f"D{n}" for n in range(1, 11))

type Verdict = Literal["done", "fail", "not_evaluated"]
type Json = dict[str, JsonValue]


def compute_verdict(statuses: Mapping[str, CheckStatus]) -> Verdict:
    """``fail`` if any fails; ``done`` only when every one of D1-D10 is present and passes."""
    if "fail" in statuses.values():
        return "fail"
    if all(statuses.get(c) == "pass" for c in ALL_CHECKS):
        return "done"
    return "not_evaluated"


def _check_number(check: str) -> int:
    return int(check[1:])


@dataclass(frozen=True, slots=True)
class DrawingReport:
    snapshot_hash: str
    snapshot: Snapshot
    geometry: GeometryCheckResult
    outcomes: Mapping[str, CheckOutcome]

    def status(self, check: str) -> CheckStatus:
        outcome = self.outcomes.get(check)
        return outcome.status if outcome is not None else self.geometry.status(check)

    @property
    def verdict(self) -> Verdict:
        return compute_verdict({c: self.status(c) for c in ALL_CHECKS})

    def _rule_failures(self) -> list[RuleFailure]:
        index = {s.key: s.index for s in self.snapshot.sheets}
        found = [f for o in self.outcomes.values() for f in o.failures]
        return sorted(found, key=lambda f: f.sort_key(index))

    def _failures_json(self) -> list[JsonValue]:
        """Document-level first, then sheet, then check; each check keeps its own order."""
        index = self.geometry.sheet_indexes
        merged: list[tuple[int, int, Json]] = [
            (index[f.sheet], _check_number(f.check), f.to_json()) for f in self.geometry.failures
        ]
        merged.extend(
            (-1 if f.sheet is None else index[f.sheet], _check_number(f.check), f.to_json())
            for f in self._rule_failures()
        )
        merged.sort(key=lambda entry: entry[:2])
        return [entry[2] for entry in merged]

    def _failure_count(self, check: str) -> int:
        outcome = self.outcomes.get(check)
        if outcome is not None:
            return len(outcome.failures)
        return sum(1 for f in self.geometry.failures if f.check == check)

    def _check_json(self, check: str) -> Json:
        outcome = self.outcomes.get(check)
        out: Json = {
            "status": self.status(check),
            "failure_count": self._failure_count(check),
            "reasons": list(outcome.reasons) if outcome is not None else [],
        }
        if outcome is not None and outcome.parts:
            out["parts"] = dict(outcome.parts)
        return out

    def _warnings_json(self) -> list[JsonValue]:
        index = self.geometry.sheet_indexes
        found: list[CheckWarning] = [w for o in self.outcomes.values() for w in o.warnings]
        found.sort(key=lambda w: (index[w.sheet], w.annotation, w.code))
        return [w.to_json() for w in found]

    def _sheets_json(self) -> Json:
        sheets: Json = {}
        for sheet in self.snapshot.sheets:
            boxes = [t for a in sheet.annotations for t in a.text_boxes]
            sheets[sheet.key] = {
                "index": sheet.index,
                "soft_metrics": self.geometry.soft_metrics[sheet.key].to_json(),
                "text_extents": {
                    "display_data": sum(1 for t in boxes if t.method == "display_data"),
                    "font_metrics": sum(1 for t in boxes if t.method == "font_metrics"),
                },
            }
        return sheets

    def to_json(self) -> JsonValue:
        failures = self._failures_json()
        snap = self.snapshot
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "drawing": {"document": snap.document, "revision": snap.revision},
            "solidworks": {"version": snap.solidworks_version, "service_pack": snap.service_pack},
            "snapshot": {
                "hash": self.snapshot_hash,
                "schema_version": snap.schema_version,
                "captured_at": snap.captured_at,
            },
            "calibration": {"status": "unverified", "note": CALIBRATION_NOTE},
            "verdict": self.verdict,
            "checks": {c: self._check_json(c) for c in ALL_CHECKS},
            "conflict_count": len(failures),
            "failures": failures,
            "warnings": self._warnings_json(),
            "sheets": self._sheets_json(),
            "thresholds": self.geometry.thresholds.to_json(),
        }


def build_report(
    doc: JsonValue,
    *,
    thresholds: CheckThresholds | None = None,
    title_block_mappings: Mapping[str, TitleBlockMapping] | None = None,
) -> DrawingReport | IssueReport:
    """Parse ``doc`` and run every check that needs no Drawing Intent."""
    snapshot = parse_snapshot(doc)
    if isinstance(snapshot, IssueReport):
        return snapshot
    t = thresholds or CheckThresholds()
    needs_intent = CheckOutcome("not_evaluated", reasons=("drawing_intent_required",))
    outcomes: dict[str, CheckOutcome] = {
        "D4": needs_intent,
        "D5": check_d5(snapshot, t),
        "D6": needs_intent,
        "D8": check_d8(snapshot, title_block_mappings or {}),
        "D9": needs_intent,
        "D10": check_d10(snapshot),
    }
    geometry = run_geometry_checks(snapshot, t)
    try:
        digest = content_hash(doc)
    except CanonicalizationError:
        return build_issue_report(
            [
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer="",
                    message="the snapshot holds a number that cannot be canonicalized",
                )
            ]
        )
    return DrawingReport(digest, snapshot, geometry, outcomes)
