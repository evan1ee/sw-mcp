"""Parsing a Drawing Geometry Snapshot into frozen dataclasses (spec 11.5.1)."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from cad_drawing.checks.snapshot import (
    SNAPSHOT_SCHEMA_ID,
    AnnotationRef,
    ArcCurve,
    PolylineCurve,
    Rebuild,
    RebuildError,
    RevisionTable,
    Snapshot,
    parse_snapshot,
)
from cad_drawing.checks.thresholds import CheckThresholds
from cad_ir.core import IssueReport, JsonValue
from cad_ir.generated import ErrorCode

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "schemas"
SNAPSHOTS = FIXTURES / "drawing-geometry-snapshot"
REVISION = 3
EDGE_COUNT = 4
HALF_OF_EPSILON = 0.02
TEXT_HEIGHT = 2.0
MINIMUM_FIELDS = 8
PARALLEL_DEG = 0.01
SCALE = 0.5


def load(kind: str, name: str) -> JsonValue:
    value: JsonValue = json.loads((SNAPSHOTS / kind / f"{name}.json").read_text(encoding="utf-8"))
    return value


def load_dict(kind: str, name: str) -> dict[str, JsonValue]:
    doc = load(kind, name)
    assert isinstance(doc, dict)
    return doc


def parsed(name: str) -> Snapshot:
    result = parse_snapshot(load("valid", name))
    assert isinstance(result, Snapshot)
    return result


def test_schema_id() -> None:
    assert SNAPSHOT_SCHEMA_ID == "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"


def test_parse_valid_fixture() -> None:
    snap = parsed("two_dimensions")
    assert snap.document == "bracket_dwg"
    assert snap.revision == REVISION
    assert len(snap.sheets) == 1
    sheet = snap.sheets[0]
    assert sheet.key == "s_0123456789"
    assert sheet.size_mm == (297.0, 210.0)
    assert [v.key for v in sheet.views] == ["v_front"]
    assert len(sheet.views[0].edges) == EDGE_COUNT
    assert [a.key for a in sheet.annotations] == ["dim_height", "dim_width"]
    width = sheet.annotations[1]
    assert width.kind == "dimension"
    assert width.view == "v_front"
    assert width.attachments == ("edge:bottom", "edge:left")
    assert width.dimension_lines == (PolylineCurve(((80.0, 78.0), (140.0, 78.0))),)
    assert [e.entity for e in width.extension_lines] == ["edge:left", "edge:right"]
    assert width.text_boxes[0].method == "display_data"
    assert len(width.text_boxes[0].corners) == len("abcd")


def test_parse_minimal_and_null_revision() -> None:
    snap = parsed("minimal")
    assert snap.sheets[0].views == ()
    assert snap.sheets[0].annotations == ()
    doc = load_dict("valid", "minimal")
    drawing = doc["drawing"]
    assert isinstance(drawing, dict)
    drawing["revision"] = None
    again = parse_snapshot(doc)
    assert isinstance(again, Snapshot)
    assert again.revision is None
    del drawing["revision"]
    assert isinstance(parse_snapshot(doc), Snapshot)


def test_parse_arc_dimension() -> None:
    annotation = parsed("angular_arc").sheets[0].annotations[0]
    assert annotation.tag == "dim_angle"
    assert annotation.view is None
    assert annotation.dimension_lines == (ArcCurve((100.0, 100.0), 20.0, 10.0, 80.0),)


def test_sheets_sorted_by_index_and_views_by_key() -> None:
    doc = load_dict("valid", "two_dimensions")
    sheets = doc["sheets"]
    assert isinstance(sheets, dict)
    first = sheets["s_0123456789"]
    assert isinstance(first, dict)
    second = json.loads(json.dumps(first))
    second["index"] = 1
    first["index"] = 2
    sheets["s_aaaaaaaaaa"] = second
    result = parse_snapshot(doc)
    assert isinstance(result, Snapshot)
    assert [(s.index, s.key) for s in result.sheets] == [(1, "s_aaaaaaaaaa"), (2, "s_0123456789")]


def test_parse_ignores_unknown_fields() -> None:
    doc = load_dict("valid", "minimal")
    doc["future_field"] = {"anything": [1, 2, 3]}
    assert isinstance(parse_snapshot(doc), Snapshot)


@pytest.mark.parametrize(
    "name", ["curve_both", "bad_sheet_key", "missing_sheets", "textbox_three_corners"]
)
def test_parse_invalid_returns_report(name: str) -> None:
    result = parse_snapshot(load("invalid", name))
    assert isinstance(result, IssueReport)
    assert result.has_errors
    assert {i.code for i in result.issues} == {ErrorCode.IR_SCHEMA_INVALID}


def test_parse_does_not_mutate_input() -> None:
    doc = load("valid", "two_dimensions")
    before = json.dumps(doc, sort_keys=True)
    parse_snapshot(doc)
    assert json.dumps(doc, sort_keys=True) == before


def test_snapshot_is_frozen() -> None:
    snap = parsed("minimal")
    with pytest.raises(FrozenInstanceError):
        snap.document = "x"  # pyright: ignore[reportAttributeAccessIssue]


def test_thresholds_defaults_and_json() -> None:
    t = CheckThresholds()
    assert (t.epsilon_mm, t.text_clearance_mm, t.line_clearance_mm) == (0.01, 0.5, 0.25)
    assert (t.edge_clearance_mm, t.font_metric_margin) == (0.25, 0.1)
    assert t.arc_chord_error_mm == t.epsilon_mm / 2
    assert t.to_json() == {
        "epsilon_mm": 0.01,
        "text_clearance_mm": 0.5,
        "line_clearance_mm": 0.25,
        "edge_clearance_mm": 0.25,
        "font_metric_margin": 0.1,
        "arc_chord_error_mm": 0.005,
        "parallel_deg": 0.01,
    }


def test_chord_error_is_derived_from_epsilon() -> None:
    t = CheckThresholds(epsilon_mm=0.04)
    assert t.arc_chord_error_mm == HALF_OF_EPSILON
    assert t.to_json()["arc_chord_error_mm"] == HALF_OF_EPSILON
    with pytest.raises(TypeError):
        CheckThresholds(arc_chord_error_mm=0.1)  # pyright: ignore[reportCallIssue]


def _first_sheet(doc: dict[str, JsonValue]) -> dict[str, JsonValue]:
    sheets = doc["sheets"]
    assert isinstance(sheets, dict)
    sheet = sheets["s_0123456789"]
    assert isinstance(sheet, dict)
    return sheet


def test_parse_quantizes_every_number_by_its_kind() -> None:
    doc = load_dict("valid", "two_dimensions")
    sheet = _first_sheet(doc)
    annotations = sheet["annotations"]
    assert isinstance(annotations, dict)
    annotation = annotations["dim_width"]
    assert isinstance(annotation, dict)
    annotation["dimension_lines"] = [
        {
            "arc": {
                "center": [100.0000004, 100.0000006],
                "radius": 20.00000049,
                "start_deg": 10.0000004,
                "end_deg": 80.0000006,
            }
        }
    ]
    annotation["text_boxes"] = [
        {
            "corners": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "height_mm": 2.0000004,
            "method": "display_data",
            "text": "x",
        }
    ]
    views = sheet["views"]
    assert isinstance(views, dict)
    view = views["v_front"]
    assert isinstance(view, dict)
    view["scale"] = 0.5000000004
    sheet["size_mm"] = [297.0000004, 210]
    result = parse_snapshot(doc)
    assert isinstance(result, Snapshot)
    parsed_sheet = result.sheets[0]
    width = parsed_sheet.annotations[1]
    assert width.dimension_lines[0] == ArcCurve((100.0, 100.000001), 20.0, 10.0, 80.000001)
    assert width.text_boxes[0].height_mm == TEXT_HEIGHT
    assert parsed_sheet.views[0].scale == SCALE
    assert parsed_sheet.size_mm == (297.0, 210.0)


def test_rectangle_with_min_above_max_is_a_rule_violation() -> None:
    doc = load_dict("valid", "two_dimensions")
    sheet = _first_sheet(doc)
    sheet["border"] = {"min": [292, 5], "max": [10, 205]}
    sheet["title_block"] = [{"min": [10, 5], "max": [100, 45]}, {"min": [10, 45], "max": [100, 5]}]
    views = sheet["views"]
    assert isinstance(views, dict)
    front = views["v_front"]
    assert isinstance(front, dict)
    front["outline"] = {"min": [0, 10], "max": [10, 0]}
    result = parse_snapshot(doc)
    assert isinstance(result, IssueReport)
    assert {i.code for i in result.issues} == {ErrorCode.IR_RULE_VIOLATED}
    assert [i.pointer for i in result.issues] == [
        "/sheets/s_0123456789/border",
        "/sheets/s_0123456789/title_block/1",
        "/sheets/s_0123456789/views/v_front/outline",
    ]


def test_rectangle_that_only_inverts_after_quantizing_is_not_repaired() -> None:
    doc = load_dict("valid", "minimal")
    sheet = _first_sheet(doc)
    sheet["border"] = {"min": [10, 5], "max": [9.9999996, 205]}  # quantizes to 10.0: equal is ok
    assert isinstance(parse_snapshot(doc), Snapshot)


def test_parse_new_fields() -> None:
    snap = parsed("checks_data")
    sheet = snap.sheets[0]
    assert sheet.sheet_format == "Test-A3.slddrt"
    assert sheet.revision_table == RevisionTable(("A", "B"))
    assert sheet.title_block_fields is not None
    names = [name for name, _ in sheet.title_block_fields]
    assert names == sorted(names)
    assert dict(sheet.title_block_fields)["material"] == "AISI 304"
    assert len(sheet.title_block_fields) == MINIMUM_FIELDS
    width, height = sheet.annotations[1], sheet.annotations[0]
    assert width.parameters == ("D1@Sketch1",)
    assert height.parameters == ("D2@Sketch1",)
    assert width.parenthesized is False
    assert snap.rebuild == Rebuild(
        completed=True, errors=(), silhouette_attachments=(), reopen="verified"
    )
    hash(sheet)


def test_parameters_are_sorted_when_parsed() -> None:
    doc = load_dict("valid", "checks_data")
    annotation = _annotation(doc, "dim_width")
    annotation["parameters"] = ["b@S", "a@S"]
    result = parse_snapshot(doc)
    assert isinstance(result, Snapshot)
    assert result.sheets[0].annotations[1].parameters == ("a@S", "b@S")


def test_parse_rebuild_entries() -> None:
    doc = load_dict("valid", "checks_data")
    doc["rebuild"] = {
        "completed": False,
        "errors": [
            {
                "kind": "dangling",
                "sheet": "s_0123456789",
                "annotation": "dim_width",
                "message": "m",
            },
            {"kind": "rebuild_error", "sheet": None, "annotation": None, "message": "n"},
        ],
        "silhouette_attachments": [{"sheet": "s_0123456789", "annotation": "dim_height"}],
        "reopen": "not_checked",
    }
    result = parse_snapshot(doc)
    assert isinstance(result, Snapshot)
    assert result.rebuild == Rebuild(
        completed=False,
        errors=(
            RebuildError("dangling", "s_0123456789", "dim_width", "m"),
            RebuildError("rebuild_error", None, None, "n"),
        ),
        silhouette_attachments=(AnnotationRef("s_0123456789", "dim_height"),),
        reopen="not_checked",
    )


def test_new_fields_default_to_none() -> None:
    snap = parsed("two_dimensions")
    sheet = snap.sheets[0]
    assert (sheet.sheet_format, sheet.title_block_fields, sheet.revision_table) == (
        None,
        None,
        None,
    )
    assert all(a.parameters is None and a.parenthesized is None for a in sheet.annotations)
    assert snap.rebuild is None


def _annotation(doc: dict[str, JsonValue], key: str) -> dict[str, JsonValue]:
    annotations = _first_sheet(doc)["annotations"]
    assert isinstance(annotations, dict)
    annotation = annotations[key]
    assert isinstance(annotation, dict)
    return annotation


def _rule_pointers(doc: dict[str, JsonValue]) -> list[str]:
    result = parse_snapshot(doc)
    assert isinstance(result, IssueReport)
    assert {i.code for i in result.issues} == {ErrorCode.IR_RULE_VIOLATED}
    return [i.pointer for i in result.issues]


def test_rebuild_unknown_sheet_is_rule_issue() -> None:
    doc = load_dict("valid", "checks_data")
    doc["rebuild"] = {
        "completed": True,
        "errors": [],
        "silhouette_attachments": [{"sheet": "s_nope", "annotation": "dim_width"}],
        "reopen": "verified",
    }
    assert _rule_pointers(doc) == ["/rebuild/silhouette_attachments/0/sheet"]


def test_rebuild_unknown_annotation_is_rule_issue() -> None:
    doc = load_dict("valid", "checks_data")
    doc["rebuild"] = {
        "completed": True,
        "errors": [
            {"kind": "dangling", "sheet": "s_0123456789", "annotation": "nope", "message": "m"}
        ],
        "silhouette_attachments": [],
        "reopen": "verified",
    }
    assert _rule_pointers(doc) == ["/rebuild/errors/0/annotation"]


def test_rebuild_unknown_sheet_in_error_is_rule_issue() -> None:
    doc = load_dict("valid", "checks_data")
    doc["rebuild"] = {
        "completed": True,
        "errors": [
            {"kind": "rebuild_error", "sheet": "s_nope", "annotation": None, "message": "m"}
        ],
        "silhouette_attachments": [],
        "reopen": "verified",
    }
    assert _rule_pointers(doc) == ["/rebuild/errors/0/sheet"]


def test_rebuild_annotation_needs_sheet() -> None:
    doc = load_dict("valid", "checks_data")
    doc["rebuild"] = {
        "completed": True,
        "errors": [{"kind": "dangling", "sheet": None, "annotation": "dim_width", "message": "m"}],
        "silhouette_attachments": [],
        "reopen": "verified",
    }
    assert _rule_pointers(doc) == ["/rebuild/errors/0/annotation"]


def test_thresholds_parallel_deg() -> None:
    t = CheckThresholds()
    assert t.parallel_deg == PARALLEL_DEG
    assert t.to_json()["parallel_deg"] == PARALLEL_DEG
