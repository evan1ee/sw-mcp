"""Stored reports for tool tests: seeded into a store, and shaped to the worst cases."""

import copy
from typing import Final, cast

from cad_ir.core.json_types import JsonValue

from cad_application.store.records import DrawingRecord, JobWarning, ReportMeta
from cad_application.testing.job_rig import DRAWING, FINGERPRINT
from cad_application.testing.tool_rig import ToolRig

type Doc = dict[str, JsonValue]

FAILURES: Final = 200
WARNINGS: Final = 120
SHEET: Final = "s_0123456789"
LONG_PATH: Final = "C:\\Work\\" + "d" * 240 + ".slddrw"
ALL_REASONS: Final = (
    "drawing_intent_required",
    "dimension_data_missing",
    "title_block_mapping_missing",
    "title_block_data_missing",
    "rebuild_data_missing",
    "reopen_not_checked",
)
# The reasons the code of the checks can give (11.5.4): D4, D6, D9 one; D5, D8 two; D10 one.
POSSIBLE_REASONS: Final = {
    "D4": ALL_REASONS[:1],
    "D5": ALL_REASONS[:2],
    "D6": ALL_REASONS[:1],
    "D8": ALL_REASONS[2:4],
    "D9": ALL_REASONS[:1],
    "D10": ALL_REASONS[4:5],
}


def base_report() -> Doc:
    """A valid report (11.5.4) in which every check passes."""
    checks: Doc = {
        f"D{n}": {"status": "pass", "failure_count": 0, "reasons": []} for n in range(1, 11)
    }
    checks["D5"] = {
        "status": "pass",
        "failure_count": 0,
        "reasons": [],
        "parts": {"auxiliary_marking": "pass", "duplicates": "pass"},
    }
    return {
        "schema_version": "0.1",
        "drawing": {"document": "bracket_dwg", "revision": 3},
        "solidworks": {"version": "2025", "service_pack": "SP3.0"},
        "snapshot": {
            "hash": "sha256:" + "0" * 64,
            "schema_version": "0.1",
            "captured_at": "2026-11-04T10:00:00Z",
        },
        "calibration": {"status": "unverified", "note": "Checks have run only on synthetic data."},
        "verdict": "done",
        "checks": checks,
        "conflict_count": 0,
        "failures": [],
        "warnings": [],
        "sheets": {
            SHEET: {
                "index": 0,
                "soft_metrics": {
                    "extension_crossings": 0,
                    "dimension_lines_over_edges": 0,
                    "view_count": 1,
                    "sheet_size_mm": [297.0, 210.0],
                },
                "text_extents": {"display_data": 2, "font_metrics": 0},
            }
        },
        "thresholds": {
            "epsilon_mm": 0.01,
            "text_clearance_mm": 0.5,
            "line_clearance_mm": 0.25,
            "edge_clearance_mm": 0.25,
            "font_metric_margin": 0.1,
            "arc_chord_error_mm": 0.005,
            "parallel_deg": 0.01,
        },
    }


def _failure(index: int) -> Doc:
    ids: list[Doc] = [{"kind": "annotation", "id": f"dim_{index}_{n}"} for n in range(5)]
    if index % 2:
        items = [{**i, "sheet": SHEET} for i in ids]
        return {
            "check": "D5",
            "sheet": SHEET,
            "code": "DRW_DUPLICATE_DIMENSION",
            "items": cast("JsonValue", items),
            "detail": {},
            "message": "m" * 80,
        }
    return {
        "check": "D1",
        "sheet": SHEET,
        "items": cast("JsonValue", ids),
        "distance_mm": 0.1,
        "threshold_mm": 0.5,
        "location": [1.0, 2.0],
        "methods": [None],
    }


def worst_report() -> Doc:
    """Every check failing, 200 failures of both kinds and 120 warnings."""
    report = base_report()
    for check in cast("dict[str, Doc]", report["checks"]).values():
        check.update(status="fail", failure_count=FAILURES, reasons=[])
    warnings: list[JsonValue] = [
        {"code": "W", "sheet": SHEET, "annotation": f"a_{n}", "message": "w" * 80}
        for n in range(WARNINGS)
    ]
    failures: list[JsonValue] = [_failure(i) for i in range(FAILURES)]
    report.update(verdict="fail", conflict_count=FAILURES, failures=failures, warnings=warnings)
    return report


def unevaluated_report() -> Doc:
    """Like ``worst_report``, but each check that can be not evaluated is, with all its reasons."""
    report = copy.deepcopy(worst_report())
    for name, check in cast("dict[str, Doc]", report["checks"]).items():
        if name in POSSIBLE_REASONS:
            reasons = cast("JsonValue", list(POSSIBLE_REASONS[name]))
            check.update(status="not_evaluated", failure_count=0, reasons=reasons)
    return report


def seed_report(rig: ToolRig, report: JsonValue, *, path: str = LONG_PATH) -> tuple[str, str]:
    """Store ``report`` with a drawing record and meta; returns (report_id, execution_id)."""
    store = rig.rig.store()
    ids = rig.rig.ids
    drawing_id, snapshot_id = ids.new_id("drw"), ids.new_id("snap")
    report_id, job_id = ids.new_id("rep"), ids.new_id("job")
    now = store.timestamp()
    store.put_drawing(
        DrawingRecord(drawing_id, path, FINGERPRINT, False, None, snapshot_id, report_id, now)
    )
    warning = JobWarning("solidworks_version_warning", "Service pack older than SP3.")
    meta = ReportMeta(report_id, job_id, drawing_id, snapshot_id, now, (warning,))
    store.put_report(report_id, report, meta)
    return report_id, job_id


def commit_job(rig: ToolRig) -> str:
    """Queue ``check_drawing`` on the default drawing and run it; returns the job ID."""
    rig.write_drawing(DRAWING)
    queued = rig.call("check_drawing", {"path": DRAWING})
    job_id = str(ToolRig.data_of(queued)["execution_id"])
    if not rig.rig.engine.run_next():
        raise AssertionError("no job ran")
    return job_id


def stored_report(rig: ToolRig, job_id: str) -> Doc:
    report_id = rig.rig.job(job_id).report_id
    if report_id is None:
        raise AssertionError(job_id)
    return rig.rig.report(report_id)[0]
