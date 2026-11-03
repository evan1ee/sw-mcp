"""The runner: fixed order, determinism and the fixture drawings (plan Task 6)."""

import copy
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cad_drawing.checks.runner import GeometryCheckResult, run_geometry_checks
from cad_drawing.checks.snapshot import Snapshot, parse_snapshot
from cad_drawing.checks.thresholds import CheckThresholds
from cad_ir.core import JsonValue, content_hash

if TYPE_CHECKING:
    from conftest import Builder

VALID = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "schemas"
    / "drawing-geometry-snapshot"
    / "valid"
)
SHEET = "s_0123456789"
OUTSIDE = 13.0


def load(name: str) -> dict[str, JsonValue]:
    doc: dict[str, JsonValue] = json.loads((VALID / f"{name}.json").read_text(encoding="utf-8"))
    return doc


def run_doc(doc: dict[str, JsonValue], t: CheckThresholds | None = None) -> GeometryCheckResult:
    snap = parse_snapshot(doc)
    assert isinstance(snap, Snapshot)
    return run_geometry_checks(snap) if t is None else run_geometry_checks(snap, t)


def annotations_of(doc: dict[str, JsonValue]) -> dict[str, JsonValue]:
    sheets = doc["sheets"]
    assert isinstance(sheets, dict)
    sheet = sheets[SHEET]
    assert isinstance(sheet, dict)
    annotations = sheet["annotations"]
    assert isinstance(annotations, dict)
    return annotations


def test_runner_on_fixture() -> None:
    result = run_doc(load("two_dimensions"))
    assert result.failures == ()
    assert result.evaluated == ("D1", "D2", "D3", "D7")
    assert [result.status(c) for c in ("D1", "D2", "D3", "D7")] == ["pass"] * 4
    assert result.thresholds == CheckThresholds()
    metrics = result.soft_metrics[SHEET]
    assert (metrics.extension_crossings, metrics.dimension_lines_over_edges) == (0, 0)
    assert metrics.view_count == 1
    for name in ("minimal", "angular_arc"):
        again = run_doc(load(name))
        assert again.failures == ()


def test_runner_finds_seeded_defects() -> None:
    doc = load("two_dimensions")
    annotations = annotations_of(doc)
    width = annotations["dim_width"]
    assert isinstance(width, dict)
    width["text_boxes"] = [
        {
            "corners": [[150, 95], [153.5, 95], [153.5, 98], [150, 98]],
            "height_mm": 3,
            "method": "display_data",
            "text": "60",
        }
    ]
    annotations["note_out"] = {
        "kind": "note",
        "native_id": "N1",
        "text_boxes": [
            {
                "corners": [[295, 100], [305, 100], [305, 103], [295, 103]],
                "height_mm": 3,
                "method": "font_metrics",
                "text": "NOTE",
            }
        ],
    }
    result = run_doc(doc)
    assert [(f.check, [i.id for i in f.items]) for f in result.failures] == [
        ("D2", ["dim_height", "dim_width"]),
        ("D7", ["note_out"]),
    ]
    d2, d7 = result.failures
    assert d2.distance_mm == 0.0
    assert d2.threshold_mm == CheckThresholds().line_clearance_mm
    assert d2.methods == (None, "display_data")
    assert d7.distance_mm == pytest.approx(OUTSIDE + 0.3, abs=1e-6)  # font-metric margin 0.3
    assert d7.methods == ("font_metrics",)
    assert [result.status(c) for c in ("D1", "D2", "D3", "D7")] == ["pass", "fail", "pass", "fail"]


def reverse_keys(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {k: reverse_keys(v) for k, v in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_keys(v) for v in value]
    return value


def test_runner_deterministic_under_key_order() -> None:
    doc = load("two_dimensions")
    annotations_of(doc)["note_out"] = {
        "kind": "note",
        "native_id": "N1",
        "text_boxes": [
            {
                "corners": [[295, 100], [305, 100], [305, 103], [295, 103]],
                "height_mm": 3,
                "method": "display_data",
                "text": "NOTE",
            },
        ],
        "dimension_lines": [{"polyline": [[100, 78], [140, 78]]}],
    }
    reversed_doc = reverse_keys(copy.deepcopy(doc))
    assert isinstance(reversed_doc, dict)
    first, second = run_doc(doc), run_doc(reversed_doc)
    assert first.failures
    assert first == second
    assert run_doc(doc) == first
    assert content_hash(first.to_json()) == content_hash(second.to_json())


def test_runner_orders_failures_by_sheet_index(b: "Builder") -> None:
    outside = b.annotation("n", dimension_lines=[b.line((100, 100), (400, 100))])
    snap = Snapshot(
        "0.1",
        "doc",
        None,
        "2025",
        "SP0",
        "2026-11-04T10:00:00Z",
        (
            b.sheet([outside], key="s_late", index=1),
            b.sheet([outside], key="s_early", index=0),
        ),
    )
    result = run_geometry_checks(snap)
    assert [f.sheet for f in result.failures] == ["s_early", "s_late"]


def test_runner_json_shape_and_thresholds_recorded() -> None:
    t = CheckThresholds(epsilon_mm=0.02)
    result = run_doc(load("two_dimensions"), t)
    out = result.to_json()
    assert isinstance(out, dict)
    assert out["thresholds"] == t.to_json()
    assert out["evaluated"] == ["D1", "D2", "D3", "D7"]
    sheets = out["sheets"]
    assert isinstance(sheets, dict)
    sheet = sheets[SHEET]
    assert isinstance(sheet, dict)
    assert sheet["D1"] == {"status": "pass", "failures": []}
    assert sheet["soft_metrics"] == {
        "extension_crossings": 0,
        "dimension_lines_over_edges": 0,
        "view_count": 1,
        "sheet_size_mm": [297.0, 210.0],
    }


def test_status_is_not_evaluated_for_checks_that_did_not_run() -> None:
    result = run_doc(load("two_dimensions"))
    assert result.status("D4") == "not_evaluated"
    assert result.status("D7") == "pass"


def test_sheet_index_is_in_the_json() -> None:
    doc = load("two_dimensions")
    sheets = doc["sheets"]
    assert isinstance(sheets, dict)
    sheet = sheets[SHEET]
    assert isinstance(sheet, dict)
    sheet["index"] = 2
    out = run_doc(doc).to_json()
    assert isinstance(out, dict)
    out_sheets = out["sheets"]
    assert isinstance(out_sheets, dict)
    entry = out_sheets[SHEET]
    assert isinstance(entry, dict)
    assert entry["index"] == 2  # noqa: PLR2004


def _gap_doc(gap: float) -> dict[str, JsonValue]:
    doc = load("minimal")
    sheets = doc["sheets"]
    assert isinstance(sheets, dict)
    sheet = next(iter(sheets.values()))
    assert isinstance(sheet, dict)
    sheet["annotations"] = {
        "a": {
            "kind": "dimension",
            "native_id": "a",
            "dimension_lines": [{"polyline": [[20, 0], [40, 0]]}],
        },
        "b": {
            "kind": "dimension",
            "native_id": "b",
            "dimension_lines": [{"polyline": [[20, gap], [40, gap]]}],
        },
    }
    return doc


def test_a_value_one_nanometre_past_a_threshold_quantizes_onto_it() -> None:
    eps = CheckThresholds().epsilon_mm
    raw = _gap_doc(eps + 1e-9)  # 1e-9 mm past epsilon: below the 1e-6 mm quantum
    stored = _gap_doc(eps)  # the same snapshot as stored, every number already quantized
    from_raw, from_stored = run_doc(raw), run_doc(stored)
    assert [f.check for f in from_raw.failures if f.check == "D1"] == ["D1"]  # onto epsilon: touch
    assert from_raw == from_stored
    assert content_hash(from_raw.to_json()) == content_hash(from_stored.to_json())
    clear = run_doc(_gap_doc(eps + 1e-5))  # a whole quantum or more past: clear
    assert clear.status("D1") == "pass"
