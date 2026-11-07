"""Unit and contract tests for Part Feature Graph IR (spec 5.7)."""

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from cad_ir.core.issues import IssueReport
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph import (
    PART_SCHEMA_ID,
    Arc,
    Circle,
    Line,
    PartGraph,
    PlaneAxes,
    SketchNode,
    SolidNode,
    parse_part_graph,
    plane_axes,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = ROOT / "schemas" / "part-feature-graph"
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "schemas" / "part-feature-graph"

EXPECTED_NODE_COUNT = 4
EXPECTED_BASE_ENTITIES_COUNT = 4
EXPECTED_HOLES_ENTITIES_COUNT = 4
EXPECTED_EXTRUDE_DEPTH = 10.0
EXPECTED_HOLE_DIAMETER = 8.0
MAX_EXAMPLE_TOKENS = 400


def _plate_doc() -> dict[str, Any]:
    return {
        "module": "part",
        "id": "plate_4h",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "l1": {"type": "line", "start": [-50, -30], "end": [50, -30]},
                    "l2": {"type": "line", "start": [50, -30], "end": [50, 30]},
                    "l3": {"type": "line", "start": [50, 30], "end": [-50, 30]},
                    "l4": {"type": "line", "start": [-50, 30], "end": [-50, -30]},
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10},
            },
            "sketch_holes": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "c1": {"type": "circle", "center": [-40, -20], "diameter": 8},
                    "c2": {"type": "circle", "center": [40, -20], "diameter": 8},
                    "c3": {"type": "circle", "center": [40, 20], "diameter": 8},
                    "c4": {"type": "circle", "center": [-40, 20], "diameter": 8},
                },
            },
            "cut_holes": {
                "type": "cut_extrude",
                "dependencies": ["sketch_holes", "extrude_base"],
                "profile": "sketch_holes",
                "end_condition": {"type": "through_all_both"},
            },
        },
    }


def test_part_schema_id_constant() -> None:
    assert PART_SCHEMA_ID == "https://sw-mcp.invalid/schemas/part-feature-graph/v0.json"


def test_plate_parses() -> None:
    doc = _plate_doc()
    res = parse_part_graph(doc)
    assert isinstance(res, PartGraph)
    assert res.id == "plate_4h"
    assert res.schema_version == "0.1"
    assert res.units == "mm"
    assert res.origin == "built"
    assert len(res.nodes) == EXPECTED_NODE_COUNT

    sketch_base = res.nodes["sketch_base"]
    assert isinstance(sketch_base, SketchNode)
    assert sketch_base.plane == "plane:front"
    assert len(sketch_base.entities) == EXPECTED_BASE_ENTITIES_COUNT
    l1 = sketch_base.entities["l1"]
    assert isinstance(l1, Line)
    assert l1.start == (-50.0, -30.0)
    assert l1.end == (50.0, -30.0)

    extrude_base = res.nodes["extrude_base"]
    assert isinstance(extrude_base, SolidNode)
    assert extrude_base.type == "extrude"
    assert extrude_base.profile == "sketch_base"
    assert extrude_base.end_condition.type == "blind"
    assert extrude_base.end_condition.depth == EXPECTED_EXTRUDE_DEPTH
    assert extrude_base.dependencies == ("sketch_base",)

    sketch_holes = res.nodes["sketch_holes"]
    assert isinstance(sketch_holes, SketchNode)
    assert len(sketch_holes.entities) == EXPECTED_HOLES_ENTITIES_COUNT
    c1 = sketch_holes.entities["c1"]
    assert isinstance(c1, Circle)
    assert c1.center == (-40.0, -20.0)
    assert c1.diameter == EXPECTED_HOLE_DIAMETER

    cut_holes = res.nodes["cut_holes"]
    assert isinstance(cut_holes, SolidNode)
    assert cut_holes.type == "cut_extrude"
    assert cut_holes.profile == "sketch_holes"
    assert cut_holes.end_condition.type == "through_all_both"
    assert cut_holes.end_condition.depth is None


def test_unknown_field_rejected() -> None:
    doc = _plate_doc()
    doc["nodes"]["extrude_base"]["suppressed"] = True
    res = parse_part_graph(doc)
    assert isinstance(res, IssueReport)
    assert any(
        i.code == ErrorCode.IR_SCHEMA_INVALID and i.pointer.startswith("/nodes/extrude_base")
        for i in res.issues
    )


def test_blind_needs_depth() -> None:
    doc = _plate_doc()
    doc["nodes"]["extrude_base"]["end_condition"] = {"type": "blind"}
    res = parse_part_graph(doc)
    assert isinstance(res, IssueReport)
    assert any(
        i.code == ErrorCode.IR_SCHEMA_INVALID
        and i.pointer.startswith("/nodes/extrude_base/end_condition")
        for i in res.issues
    )


def test_through_all_has_no_depth() -> None:
    doc = _plate_doc()
    doc["nodes"]["cut_holes"]["end_condition"] = {"type": "through_all_both", "depth": 10}
    res = parse_part_graph(doc)
    assert isinstance(res, IssueReport)
    assert any(
        i.code == ErrorCode.IR_SCHEMA_INVALID
        and i.pointer.startswith("/nodes/cut_holes/end_condition")
        for i in res.issues
    )


def test_model_matches_schema() -> None:
    sketch_path = SCHEMAS_DIR / "features" / "sketch.json"
    extrude_path = SCHEMAS_DIR / "features" / "extrude.json"
    cut_path = SCHEMAS_DIR / "features" / "cut_extrude.json"

    sketch_schema = json.loads(sketch_path.read_text(encoding="utf-8"))
    extrude_schema = json.loads(extrude_path.read_text(encoding="utf-8"))
    cut_schema = json.loads(cut_path.read_text(encoding="utf-8"))

    sketch_fields = {f.name for f in fields(SketchNode)}
    assert set(sketch_schema["properties"].keys()) == sketch_fields

    solid_fields = {f.name for f in fields(SolidNode)}
    assert set(extrude_schema["properties"].keys()) == solid_fields
    assert set(cut_schema["properties"].keys()) == solid_fields


def test_examples_within_budget() -> None:
    for feature_path in (SCHEMAS_DIR / "features").glob("*.json"):
        doc = json.loads(feature_path.read_text(encoding="utf-8"))
        assert "examples" in doc
        assert len(doc["examples"]) >= 1
        example = doc["examples"][0]
        compact = json.dumps(example, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        tokens = len(compact) / 4
        msg = f"{feature_path.name} example exceeds budget ({tokens})"
        assert tokens <= MAX_EXAMPLE_TOKENS, msg


def test_plane_axes() -> None:
    front = plane_axes("plane:front")
    assert isinstance(front, PlaneAxes)
    assert front.plane == "plane:front"
    assert front.x_axis == (1.0, 0.0, 0.0)
    assert front.y_axis == (0.0, 1.0, 0.0)
    assert front.normal == (0.0, 0.0, 1.0)
    assert front.to_model(10.0, 20.0, 30.0) == (10.0, 20.0, 30.0)

    top = plane_axes("plane:top")
    assert top.plane == "plane:top"
    assert top.x_axis == (1.0, 0.0, 0.0)
    assert top.y_axis == (0.0, 0.0, -1.0)
    assert top.normal == (0.0, 1.0, 0.0)
    assert top.to_model(10.0, 20.0, 30.0) == (10.0, 30.0, -20.0)

    right = plane_axes("plane:right")
    assert right.plane == "plane:right"
    assert right.x_axis == (0.0, 0.0, -1.0)
    assert right.y_axis == (0.0, 1.0, 0.0)
    assert right.normal == (1.0, 0.0, 0.0)
    assert right.to_model(10.0, 20.0, 30.0) == (30.0, 20.0, -10.0)


def test_plane_axes_unsupported() -> None:
    with pytest.raises(ValueError, match="unknown or unsupported plane"):
        plane_axes("plane:isometric")


def test_part_graph_roundtrip() -> None:
    doc = _plate_doc()
    res = parse_part_graph(doc)
    assert isinstance(res, PartGraph)
    out = res.to_dict()
    assert out["module"] == "part"
    assert out["id"] == "plate_4h"
    assert out["schema_version"] == "0.1"
    assert out["units"] == "mm"
    assert out["origin"] == "built"
    assert len(out["nodes"]) == EXPECTED_NODE_COUNT
    assert out["nodes"]["extrude_base"]["end_condition"] == {"type": "blind", "depth": 10.0}
    assert out["nodes"]["cut_holes"]["end_condition"] == {"type": "through_all_both"}


def test_arc_dataclass_and_parsing() -> None:
    doc: dict[str, Any] = {
        "module": "part",
        "id": "plate_slot",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "l1": {"type": "line", "start": [-20, -10], "end": [20, -10]},
                    "a1": {
                        "type": "arc",
                        "center": [20, 0],
                        "start": [20, -10],
                        "end": [20, 10],
                        "direction": "ccw",
                    },
                    "l2": {"type": "line", "start": [20, 10], "end": [-20, 10]},
                    "a2": {
                        "type": "arc",
                        "center": [-20, 0],
                        "start": [-20, 10],
                        "end": [-20, -10],
                        "direction": "ccw",
                    },
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 5.0},
            },
        },
    }
    res = parse_part_graph(doc)
    assert isinstance(res, PartGraph)
    sketch = res.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    a1 = sketch.entities["a1"]
    assert isinstance(a1, Arc)
    assert a1.center == (20.0, 0.0)
    assert a1.start == (20.0, -10.0)
    assert a1.end == (20.0, 10.0)
    assert a1.direction == "ccw"
    assert a1.type == "arc"
    assert a1.to_dict() == {
        "type": "arc",
        "center": [20.0, 0.0],
        "start": [20.0, -10.0],
        "end": [20.0, 10.0],
        "direction": "ccw",
    }
