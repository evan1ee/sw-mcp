"""Check primitives built from a sheet (spec 11.5.2 primitives table)."""

import copy
import json
import math
from collections.abc import Sequence
from pathlib import Path

import pytest
from cad_drawing.checks.geometry2d import Segment, aabb
from cad_drawing.checks.primitives import Prim, sheet_primitives
from cad_drawing.checks.snapshot import Sheet, Snapshot, parse_snapshot
from cad_drawing.checks.thresholds import CheckThresholds
from cad_ir.core import JsonValue

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "schemas"
    / "drawing-geometry-snapshot"
    / "valid"
    / "two_dimensions.json"
)
T = CheckThresholds()
SHEET = "s_0123456789"


def fixture_doc() -> dict[str, JsonValue]:
    doc: dict[str, JsonValue] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc


def parse_sheet(doc: dict[str, JsonValue]) -> Sheet:
    result = parse_snapshot(doc)
    assert isinstance(result, Snapshot)
    return result.sheets[0]


def sheet_with(annotations: dict[str, JsonValue], edges: list[JsonValue] | None = None) -> Sheet:
    doc = fixture_doc()
    sheets = doc["sheets"]
    assert isinstance(sheets, dict)
    sheet = sheets[SHEET]
    assert isinstance(sheet, dict)
    sheet["annotations"] = annotations
    if edges is not None:
        views = sheet["views"]
        assert isinstance(views, dict)
        front = views["v_front"]
        assert isinstance(front, dict)
        front["edges"] = edges
    return parse_sheet(doc)


def text_annotation(
    corners: Sequence[Sequence[float]], method: str, height: float
) -> dict[str, JsonValue]:
    box: dict[str, JsonValue] = {
        "corners": json.loads(json.dumps(corners)),
        "height_mm": height,
        "method": method,
        "text": "x",
    }
    return {"kind": "note", "native_id": "n", "text_boxes": [box]}


def only(prims: tuple[Prim, ...], kind: str) -> Prim:
    found = [p for p in prims if p.kind == kind]
    assert len(found) == 1
    return found[0]


def test_primitives_of_fixture() -> None:
    prims = sheet_primitives(parse_sheet(fixture_doc()), T)
    edge_prims = [p for p in prims if p.kind == "edge"]
    assert [(p.owner, p.index) for p in edge_prims] == [("v_front", i) for i in range(4)]
    ext = [p for p in prims if p.kind == "extension_line" and p.owner == "dim_width"]
    assert [p.entity for p in ext] == ["edge:left", "edge:right"]
    assert all(p.entity is None for p in prims if p.kind != "extension_line")
    arrows = [p for p in prims if p.kind == "arrowhead"]
    assert len(arrows) == len("abcd")
    assert all(p.polygon is not None and len(p.segments) == len("abc") for p in arrows)
    boxes = [p for p in prims if p.kind == "text_box"]
    assert len(boxes) == len("ab")
    assert all(p.polygon is not None and p.method == "display_data" for p in boxes)


def test_output_order_is_deterministic() -> None:
    doc = fixture_doc()
    reversed_doc = copy.deepcopy(doc)
    sheets = reversed_doc["sheets"]
    assert isinstance(sheets, dict)
    sheet = sheets[SHEET]
    assert isinstance(sheet, dict)
    annotations = sheet["annotations"]
    assert isinstance(annotations, dict)
    sheet["annotations"] = dict(reversed(list(annotations.items())))
    assert sheet_primitives(parse_sheet(doc), T) == sheet_primitives(parse_sheet(reversed_doc), T)
    owners = [(p.owner, p.kind, p.index) for p in sheet_primitives(parse_sheet(doc), T)]
    assert [o for o, _, _ in owners] == sorted(o for o, _, _ in owners)


def test_font_metric_box_inflated() -> None:
    corners = [[0, 0], [10, 0], [10, 2], [0, 2]]
    prims = sheet_primitives(sheet_with({"a": text_annotation(corners, "font_metrics", 2)}), T)
    box = only(prims, "text_box")
    assert box.method == "font_metrics"
    assert box.polygon is not None
    # margin 0.1 x height 2 = 0.2 on every side
    assert aabb(box.polygon) == pytest.approx((-0.2, -0.2, 10.2, 2.2), abs=1e-12)


def test_display_data_box_not_inflated() -> None:
    corners = [[0, 0], [10, 0], [10, 2], [0, 2]]
    prims = sheet_primitives(sheet_with({"a": text_annotation(corners, "display_data", 2)}), T)
    box = only(prims, "text_box")
    assert box.polygon is not None
    assert aabb(box.polygon) == (0, 0, 10, 2)


def test_leader_is_dimension_line() -> None:
    ann: dict[str, JsonValue] = {
        "kind": "callout",
        "native_id": "c",
        "dimension_lines": [{"polyline": [[0, 0], [5, 0]]}],
        "leaders": [[[5, 0], [8, 3], [12, 3]]],
    }
    prims = sheet_primitives(sheet_with({"c": ann}), T)
    lines = [p for p in prims if p.kind == "dimension_line"]
    assert [len(p.segments) for p in lines] == [1, 2]
    assert [p.index for p in lines] == [0, 1]
    assert {p.kind for p in prims if p.owner == "c"} == {"dimension_line"}


def test_arc_dimension_tessellated() -> None:
    arc: dict[str, JsonValue] = {"center": [0, 0], "radius": 20, "start_deg": 0, "end_deg": 90}
    ann: dict[str, JsonValue] = {
        "kind": "dimension",
        "native_id": "d",
        "dimension_lines": [{"arc": arc}],
    }
    line = only(sheet_primitives(sheet_with({"d": ann}), T), "dimension_line")
    assert len(line.segments) > len("ab")
    for s in line.segments:
        for p in (s.a, s.b):
            assert math.hypot(*p) == pytest.approx(20.0, abs=1e-9)
    mids = [math.hypot((s.a[0] + s.b[0]) / 2, (s.a[1] + s.b[1]) / 2) for s in line.segments]
    assert all(20 - m <= T.arc_chord_error_mm + 1e-12 for m in mids)


def test_degenerate_arc_and_box() -> None:
    zero_arc: dict[str, JsonValue] = {"center": [0, 0], "radius": 5, "start_deg": 40, "end_deg": 40}
    point_box: dict[str, JsonValue] = {
        "corners": [[1, 1], [1, 1], [1, 1], [1, 1]],
        "height_mm": 0,
        "method": "font_metrics",
        "text": "",
    }
    flat_box: dict[str, JsonValue] = {
        "corners": [[0, 0], [10, 0], [10, 0], [0, 0]],
        "height_mm": 0,
        "method": "display_data",
        "text": "",
    }
    ann: dict[str, JsonValue] = {
        "kind": "dimension",
        "native_id": "d",
        "dimension_lines": [{"arc": zero_arc}, {"polyline": [[3, 3], [3, 3]]}],
        "text_boxes": [point_box, flat_box],
    }
    prims = sheet_primitives(sheet_with({"d": ann}), T)
    lines = [p for p in prims if p.kind == "dimension_line"]
    assert [p.segments for p in lines] == [(), ()]
    boxes = [p for p in prims if p.kind == "text_box"]
    assert len(boxes) == len("ab")
    assert all(b.polygon is not None for b in boxes)
    assert Segment((0, 0), (10, 0)) in boxes[1].segments


def test_every_arrowhead_gets_its_polygon() -> None:
    ann: dict[str, JsonValue] = {
        "kind": "dimension",
        "native_id": "d",
        "arrowheads": [
            {"polygon": [[0, 0], [2, 0], [2, 1], [0, 1]]},
            {"polygon": [[0, 0], [1, 0], [0, 1]]},
        ],
    }
    arrows = [p for p in sheet_primitives(sheet_with({"d": ann}), T) if p.kind == "arrowhead"]
    assert [len(p.polygon or ()) for p in arrows] == [4, 3]
    assert [p.index for p in arrows] == [0, 1]


def test_edges_of_every_kind_included() -> None:
    kinds = ["visible", "silhouette", "hidden", "centerline", "center_mark"]
    edges: list[JsonValue] = [
        {"curve": {"polyline": [[0, i], [10, i]]}, "kind": kind} for i, kind in enumerate(kinds)
    ]
    prims = sheet_primitives(sheet_with({}, edges), T)
    assert [(p.owner, p.index) for p in prims if p.kind == "edge"] == [
        ("v_front", i) for i in range(len(kinds))
    ]


def _line_work_annotation(kind: str) -> dict[str, JsonValue]:
    return {
        "kind": kind,
        "native_id": kind,
        "dimension_lines": [{"polyline": [[0, 0], [5, 0]]}],
        "leaders": [[[5, 0], [8, 3]]],
        "extension_lines": [{"line": [[0, 0], [0, 2]], "entity": "e"}],
    }


def test_center_mark_and_centerline_line_work_become_edge_prims() -> None:
    annotations: dict[str, JsonValue] = {
        "cm": _line_work_annotation("center_mark"),
        "cl": _line_work_annotation("centerline"),
        "d": _line_work_annotation("dimension"),
    }
    prims = sheet_primitives(sheet_with(annotations), T)
    edges = [
        (p.owner, p.index, p.edge_kind, p.in_view)
        for p in prims
        if p.kind == "edge" and p.owner != "v_front"
    ]
    assert edges == [
        ("cl", 0, "centerline", False),
        ("cl", 1, "centerline", False),
        ("cm", 0, "center_mark", False),
        ("cm", 1, "center_mark", False),
    ]
    lines = [(p.owner, p.leader) for p in prims if p.kind == "dimension_line"]
    assert lines == [("d", False), ("d", True)]
    assert {p.owner for p in prims if p.kind == "extension_line"} == {"cm", "cl", "d"}


def test_view_edges_carry_kind_and_view_flag() -> None:
    edges: list[JsonValue] = [{"curve": {"polyline": [[0, 0], [10, 0]]}, "kind": "silhouette"}]
    (edge,) = [p for p in sheet_primitives(sheet_with({}, edges), T) if p.kind == "edge"]
    assert (edge.edge_kind, edge.in_view, edge.leader) == ("silhouette", True, False)


def test_full_circle_dimension_written_through_radians_is_tessellated_whole() -> None:
    arc: dict[str, JsonValue] = {
        "center": [0, 0],
        "radius": 20,
        "start_deg": 109.14694036038935,
        "end_deg": 469.1469403603894,
    }
    ann: dict[str, JsonValue] = {
        "kind": "dimension",
        "native_id": "d",
        "dimension_lines": [{"arc": arc}],
    }
    line = only(sheet_primitives(sheet_with({"d": ann}), T), "dimension_line")
    assert len(line.segments) > len("abcdefghij")
