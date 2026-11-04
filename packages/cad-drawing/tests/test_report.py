"""The drawing report: verdict, determinism and schema (spec 11.5.4)."""

import copy
import json
from pathlib import Path

import pytest
from cad_drawing.checks.d8 import TitleBlockMapping
from cad_drawing.checks.outcome import CheckStatus
from cad_drawing.checks.report import (
    ALL_CHECKS,
    CALIBRATION_NOTE,
    REPORT_SCHEMA_ID,
    DrawingReport,
    build_report,
    compute_verdict,
)
from cad_drawing.checks.thresholds import CheckThresholds
from cad_ir.core import (
    IssueReport,
    JsonValue,
    canonical_bytes,
    validate_against_schema,
)
from cad_ir.generated import ErrorCode

ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "schemas"
SNAPSHOTS = ROOT / "drawing-geometry-snapshot" / "valid"
GOLDEN = ROOT / "drawing-report" / "valid" / "checks_data.json"
SHEET = "s_0123456789"
TEMPLATE = "Test-A3.slddrt"
MAPPINGS = {TEMPLATE: TitleBlockMapping(TEMPLATE, revision_table=True)}
CONFLICTS = 4

type Doc = dict[str, JsonValue]


def load(name: str) -> Doc:
    doc: Doc = json.loads((SNAPSHOTS / f"{name}.json").read_text(encoding="utf-8"))
    return doc


def obj(value: JsonValue) -> Doc:
    assert isinstance(value, dict)
    return value


def sheet_of(doc: Doc) -> Doc:
    return obj(obj(doc["sheets"])[SHEET])


def annotations_of(doc: Doc) -> Doc:
    return obj(sheet_of(doc)["annotations"])


def report_of(doc: Doc, **kwargs: object) -> DrawingReport:
    result = build_report(doc, **kwargs)  # pyright: ignore[reportArgumentType]
    assert isinstance(result, DrawingReport)
    return result


def seeded() -> Doc:
    """A duplicate parameter, a dangling dimension, an empty title field and a D2 overlap."""
    doc = load("checks_data")
    annotations = annotations_of(doc)
    obj(annotations["dim_height"])["parameters"] = ["D1@Sketch1"]
    annotations["note_a"] = {
        "kind": "note",
        "native_id": "Note1",
        "text_boxes": [
            {
                "corners": [[108, 81], [116, 81], [116, 84], [108, 84]],
                "height_mm": 3,
                "method": "display_data",
                "text": "NOTE",
            }
        ],
    }
    obj(obj(sheet_of(doc)["title_block_fields"]))["material"] = ""
    doc["rebuild"] = {
        "completed": True,
        "errors": [
            {
                "kind": "dangling",
                "sheet": SHEET,
                "annotation": "dim_width",
                "message": "dimension lost its reference",
            }
        ],
        "silhouette_attachments": [],
        "reopen": "verified",
    }
    return doc


def reversed_keys(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {k: reversed_keys(value[k]) for k in reversed(list(value))}
    if isinstance(value, list):
        return [reversed_keys(v) for v in value]
    return value


def test_compute_verdict() -> None:
    every: dict[str, CheckStatus] = dict.fromkeys(ALL_CHECKS, "pass")
    assert compute_verdict(every) == "done"
    assert compute_verdict({**every, "D4": "not_evaluated"}) == "not_evaluated"
    assert compute_verdict({**every, "D4": "not_evaluated", "D8": "fail"}) == "fail"
    assert compute_verdict({k: v for k, v in every.items() if k != "D9"}) == "not_evaluated"
    assert compute_verdict({}) == "not_evaluated"
    assert tuple(f"D{n}" for n in range(1, 11)) == ALL_CHECKS


def test_clean_full_snapshot_is_not_done() -> None:
    report = report_of(load("checks_data"), title_block_mappings=MAPPINGS)
    out = obj(report.to_json())
    checks = obj(out["checks"])
    status = {c: obj(checks[c])["status"] for c in ALL_CHECKS}
    assert status == {
        "D1": "pass",
        "D2": "pass",
        "D3": "pass",
        "D4": "not_evaluated",
        "D5": "not_evaluated",
        "D6": "not_evaluated",
        "D7": "pass",
        "D8": "pass",
        "D9": "not_evaluated",
        "D10": "pass",
    }
    assert report.verdict == "not_evaluated"
    assert out["verdict"] == "not_evaluated"
    assert out["calibration"] == {"status": "unverified", "note": CALIBRATION_NOTE}
    assert out["conflict_count"] == 0
    assert out["failures"] == []
    assert obj(checks["D5"])["parts"] == {
        "auxiliary_marking": "not_evaluated",
        "duplicates": "pass",
    }
    assert obj(checks["D4"])["reasons"] == ["drawing_intent_required"]


def test_old_snapshot_all_new_checks_not_evaluated() -> None:
    report = report_of(load("two_dimensions"))
    assert report.status("D8") == "not_evaluated"
    assert report.status("D10") == "not_evaluated"
    assert report.status("D5") == "not_evaluated"
    checks = obj(obj(report.to_json())["checks"])
    assert report.outcomes["D5"].reasons == ("drawing_intent_required", "dimension_data_missing")
    assert obj(checks["D8"])["reasons"] == ["title_block_mapping_missing"]
    assert obj(checks["D10"])["reasons"] == ["rebuild_data_missing"]
    assert report.verdict == "not_evaluated"


def test_seeded_defects_fail_verdict() -> None:
    report = report_of(seeded(), title_block_mappings=MAPPINGS)
    out = obj(report.to_json())
    assert report.verdict == "fail"
    assert out["verdict"] == "fail"
    assert out["conflict_count"] == CONFLICTS
    failures = out["failures"]
    assert isinstance(failures, list)
    ordered = [(obj(f)["check"], obj(f).get("code")) for f in failures]
    assert ordered == [
        ("D2", None),
        ("D5", "duplicate_parameter"),
        ("D8", "title_field_unfilled"),
        ("D10", "dangling"),
    ]
    checks = obj(out["checks"])
    assert {c: obj(checks[c])["failure_count"] for c in ("D2", "D5", "D8", "D10")} == dict.fromkeys(
        ("D2", "D5", "D8", "D10"), 1
    )


def test_document_level_failures_come_first() -> None:
    doc = seeded()
    obj(doc["rebuild"])["reopen"] = "failed"
    out = obj(report_of(doc, title_block_mappings=MAPPINGS).to_json())
    failures = out["failures"]
    assert isinstance(failures, list)
    first = obj(failures[0])
    assert (first["code"], first["sheet"]) == ("reopen_failed", None)
    assert out["conflict_count"] == CONFLICTS + 1


def test_report_output_matches_schema() -> None:
    reports: list[JsonValue] = []
    for name in ("minimal", "angular_arc", "two_dimensions", "checks_data"):
        reports.append(report_of(load(name)).to_json())
        reports.append(report_of(load(name), title_block_mappings=MAPPINGS).to_json())
    reports.append(report_of(seeded(), title_block_mappings=MAPPINGS).to_json())
    for out in reports:
        assert validate_against_schema(out, REPORT_SCHEMA_ID) == ()


def test_golden_report_fixture() -> None:
    expected: JsonValue = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = report_of(load("checks_data"), title_block_mappings=MAPPINGS)
    assert report.to_json() == expected


def test_report_deterministic_under_key_order() -> None:
    doc = load("checks_data")
    flipped = obj(reversed_keys(doc))
    a = report_of(doc, title_block_mappings=MAPPINGS)
    b = report_of(flipped, title_block_mappings=MAPPINGS)
    assert canonical_bytes(a.to_json()) == canonical_bytes(b.to_json())
    assert obj(obj(a.to_json())["snapshot"])["hash"] == obj(obj(b.to_json())["snapshot"])["hash"]


def test_invalid_snapshot_returns_issue_report() -> None:
    doc = load("checks_data")
    del doc["sheets"]
    assert isinstance(build_report(doc), IssueReport)


def test_text_extents_counted() -> None:
    doc = load("checks_data")
    annotations_of(doc)["note_a"] = {
        "kind": "note",
        "native_id": "Note1",
        "text_boxes": [
            {
                "corners": [[200, 100], [210, 100], [210, 103], [200, 103]],
                "height_mm": 3,
                "method": "font_metrics",
                "text": "A",
            },
            {
                "corners": [[200, 110], [210, 110], [210, 113], [200, 113]],
                "height_mm": 3,
                "method": "display_data",
                "text": "B",
            },
        ],
    }
    sheets = obj(obj(report_of(doc).to_json())["sheets"])
    entry = obj(sheets[SHEET])
    assert entry["index"] == 0
    assert entry["text_extents"] == {"display_data": 3, "font_metrics": 1}
    assert set(obj(entry["soft_metrics"])) >= {"extension_crossings", "view_count"}


def test_thresholds_recorded() -> None:
    custom = CheckThresholds(epsilon_mm=0.02, parallel_deg=0.5)
    out = obj(report_of(load("checks_data"), thresholds=custom).to_json())
    assert out["thresholds"] == custom.to_json()
    default = obj(report_of(load("checks_data")).to_json())
    assert default["thresholds"] == CheckThresholds().to_json()


def test_report_does_not_mutate_input() -> None:
    doc = seeded()
    before = copy.deepcopy(doc)
    report_of(doc, title_block_mappings=MAPPINGS).to_json()
    assert doc == before


@pytest.mark.parametrize("check", ["D4", "D6", "D9"])
def test_intent_checks_are_not_evaluated(check: str) -> None:
    report = report_of(load("checks_data"), title_block_mappings=MAPPINGS)
    assert report.status(check) == "not_evaluated"


def test_unsafe_integer_returns_issue_report() -> None:
    doc = load("checks_data")
    sheet_of(doc)["size_mm"] = [10**20, 210]
    result = build_report(doc)
    assert isinstance(result, IssueReport)
    (issue,) = result.issues
    assert issue.code == ErrorCode.IR_RULE_VIOLATED
    assert issue.pointer == ""
