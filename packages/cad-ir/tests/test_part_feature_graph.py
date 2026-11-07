"""Unit and contract tests for Part Feature Graph IR (spec 5.7)."""

import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Final, cast

import pytest
from cad_ir.core.issues import IssueReport
from cad_ir.core.json_types import JsonValue
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph import (
    PART_SCHEMA_ID,
    Arc,
    CenterRectangle,
    Circle,
    CircularPattern,
    CornerRectangle,
    CutRevolve,
    Line,
    LinearPattern,
    LinearPatternDirection,
    Mirror,
    PartGraph,
    PlaneAxes,
    Revolve,
    SketchNode,
    SolidNode,
    StraightSlot,
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
SLOT_WIDTH = 15.0
MAX_EXAMPLE_TOKENS = 400
RECT_W: Final[float] = 100.0
RECT_H: Final[float] = 60.0


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
    res = parse_part_graph(cast(JsonValue, doc))
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
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, IssueReport)
    assert any(
        i.code == ErrorCode.IR_SCHEMA_INVALID and i.pointer.startswith("/nodes/extrude_base")
        for i in res.issues
    )


def test_blind_needs_depth() -> None:
    doc = _plate_doc()
    doc["nodes"]["extrude_base"]["end_condition"] = {"type": "blind"}
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, IssueReport)
    assert any(
        i.code == ErrorCode.IR_SCHEMA_INVALID
        and i.pointer.startswith("/nodes/extrude_base/end_condition")
        for i in res.issues
    )


def test_through_all_has_no_depth() -> None:
    doc = _plate_doc()
    doc["nodes"]["cut_holes"]["end_condition"] = {"type": "through_all_both", "depth": 10}
    res = parse_part_graph(cast(JsonValue, doc))
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
    res = parse_part_graph(cast(JsonValue, doc))
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
    res = parse_part_graph(cast(JsonValue, doc))
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


def test_corner_rectangle_parses() -> None:
    doc: dict[str, Any] = {
        "module": "part",
        "id": "corner_rect_part",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "r1": {
                        "type": "corner_rectangle",
                        "corner1": [-50.0, -30.0],
                        "corner2": [50.0, 30.0],
                    }
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10.0},
            },
        },
    }
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, PartGraph)
    sketch = res.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    r1 = sketch.entities["r1"]
    assert isinstance(r1, CornerRectangle)
    assert r1.corner1 == (-50.0, -30.0)
    assert r1.corner2 == (50.0, 30.0)
    assert r1.type == "corner_rectangle"
    assert r1.to_dict() == {
        "type": "corner_rectangle",
        "corner1": [-50.0, -30.0],
        "corner2": [50.0, 30.0],
    }


def test_center_rectangle_parses() -> None:
    doc: dict[str, Any] = {
        "module": "part",
        "id": "center_rect_part",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "r1": {
                        "type": "center_rectangle",
                        "center": [0.0, 0.0],
                        "width": RECT_W,
                        "height": RECT_H,
                    }
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10.0},
            },
        },
    }
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, PartGraph)
    sketch = res.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    r1 = sketch.entities["r1"]
    assert isinstance(r1, CenterRectangle)
    assert r1.center == (0.0, 0.0)
    assert r1.width == RECT_W
    assert r1.height == RECT_H
    assert r1.type == "center_rectangle"
    assert r1.to_dict() == {
        "type": "center_rectangle",
        "center": [0.0, 0.0],
        "width": RECT_W,
        "height": RECT_H,
    }


def test_straight_slot_parses() -> None:
    doc: dict[str, Any] = {
        "module": "part",
        "id": "straight_slot_part",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "s1": {
                        "type": "straight_slot",
                        "start_point": [-20.0, 0.0],
                        "end_point": [20.0, 0.0],
                        "width": SLOT_WIDTH,
                    }
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10.0},
            },
        },
    }
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, PartGraph)
    sketch = res.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    s1 = sketch.entities["s1"]
    assert isinstance(s1, StraightSlot)
    assert s1.start_point == (-20.0, 0.0)
    assert s1.end_point == (20.0, 0.0)
    assert s1.width == SLOT_WIDTH
    assert s1.type == "straight_slot"
    assert s1.to_dict() == {
        "type": "straight_slot",
        "start_point": [-20.0, 0.0],
        "end_point": [20.0, 0.0],
        "width": SLOT_WIDTH,
    }


def test_linear_pattern_parses() -> None:
    doc = {
        "module": "part",
        "id": "pattern_part",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "r1": {
                        "type": "center_rectangle",
                        "center": [0.0, 0.0],
                        "width": 100.0,
                        "height": 60.0,
                    }
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10.0},
            },
            "sketch_hole": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "c1": {
                        "type": "circle",
                        "center": [-30.0, 0.0],
                        "diameter": 10.0,
                    }
                },
            },
            "cut_hole": {
                "type": "cut_extrude",
                "dependencies": ["sketch_hole", "extrude_base"],
                "profile": "sketch_hole",
                "end_condition": {"type": "through_all_both"},
            },
            "pattern_holes": {
                "type": "linear_pattern",
                "dependencies": ["cut_hole", "extrude_base"],
                "seeds": ["cut_hole"],
                "direction_1": {
                    "direction": "plane:right",
                    "spacing": 20.0,
                    "count": 4,
                },
            },
        },
    }
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, PartGraph)
    pat = res.nodes["pattern_holes"]
    assert isinstance(pat, LinearPattern)
    assert pat.type == "linear_pattern"
    assert pat.seeds == ("cut_hole",)
    assert pat.direction_1 == LinearPatternDirection(
        direction="plane:right", spacing=20.0, count=4, reverse=False
    )
    assert pat.direction_2 is None


def test_circular_pattern_parses() -> None:
    doc = {
        "module": "part",
        "id": "circular_pattern_part",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "c1": {
                        "type": "circle",
                        "center": [0.0, 0.0],
                        "diameter": 100.0,
                    }
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10.0},
            },
            "sketch_hole": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "c2": {
                        "type": "circle",
                        "center": [35.0, 0.0],
                        "diameter": 10.0,
                    }
                },
            },
            "cut_hole": {
                "type": "cut_extrude",
                "dependencies": ["sketch_hole", "extrude_base"],
                "profile": "sketch_hole",
                "end_condition": {"type": "through_all_both"},
            },
            "pattern_holes": {
                "type": "circular_pattern",
                "dependencies": ["cut_hole", "extrude_base"],
                "seeds": ["cut_hole"],
                "axis": "plane:front",
                "count": 6,
                "spacing": 360.0,
                "equal_spacing": True,
            },
        },
    }
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, PartGraph)
    pat = res.nodes["pattern_holes"]
    assert isinstance(pat, CircularPattern)
    assert pat.type == "circular_pattern"
    assert pat.seeds == ("cut_hole",)
    assert pat.axis == "plane:front"
    expected_count = 6
    expected_spacing = 360.0
    assert pat.count == expected_count
    assert pat.spacing == expected_spacing
    assert pat.equal_spacing is True
    assert pat.reverse is False


def test_parse_mirror_feature() -> None:
    doc = {
        "module": "part",
        "id": "mirror_part",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "l1": {"type": "line", "start": [-50.0, -25.0], "end": [50.0, -25.0]},
                    "l2": {"type": "line", "start": [50.0, -25.0], "end": [50.0, 25.0]},
                    "l3": {"type": "line", "start": [50.0, 25.0], "end": [-50.0, 25.0]},
                    "l4": {"type": "line", "start": [-50.0, 25.0], "end": [-50.0, -25.0]},
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10.0},
            },
            "sketch_hole": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "c1": {
                        "type": "circle",
                        "center": [25.0, 0.0],
                        "diameter": 10.0,
                    }
                },
            },
            "cut_hole": {
                "type": "cut_extrude",
                "dependencies": ["sketch_hole", "extrude_base"],
                "profile": "sketch_hole",
                "end_condition": {"type": "through_all_both"},
            },
            "mirror_hole": {
                "type": "mirror",
                "dependencies": ["cut_hole", "extrude_base"],
                "seeds": ["cut_hole"],
                "plane": "plane:right",
                "merge": True,
            },
        },
    }
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, PartGraph)
    mir = res.nodes["mirror_hole"]
    assert isinstance(mir, Mirror)
    assert mir.type == "mirror"
    assert mir.seeds == ("cut_hole",)
    assert mir.plane == "plane:right"
    assert mir.merge is True


def test_revolve_and_cut_revolve_dataclass_and_parsing() -> None:
    doc: dict[str, Any] = {
        "module": "part",
        "id": "turned_shaft",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_shaft": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "cl": {
                        "type": "line",
                        "start": [0.0, 0.0],
                        "end": [0.0, 50.0],
                        "construction": True,
                    },
                    "l1": {"type": "line", "start": [0.0, 0.0], "end": [15.0, 0.0]},
                    "l2": {"type": "line", "start": [15.0, 0.0], "end": [15.0, 50.0]},
                    "l3": {"type": "line", "start": [15.0, 50.0], "end": [0.0, 50.0]},
                    "l4": {"type": "line", "start": [0.0, 50.0], "end": [0.0, 0.0]},
                },
            },
            "shaft_body": {
                "type": "revolve",
                "dependencies": ["sketch_shaft"],
                "profile": "sketch_shaft",
                "axis": "sketch_shaft.cl",
                "angle": 360.0,
                "merge_result": True,
            },
            "sketch_groove": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "cl": {
                        "type": "line",
                        "start": [0.0, 0.0],
                        "end": [0.0, 50.0],
                        "construction": True,
                    },
                    "g1": {"type": "line", "start": [12.0, 20.0], "end": [15.0, 20.0]},
                    "g2": {"type": "line", "start": [15.0, 20.0], "end": [15.0, 25.0]},
                    "g3": {"type": "line", "start": [15.0, 25.0], "end": [12.0, 25.0]},
                    "g4": {"type": "line", "start": [12.0, 25.0], "end": [12.0, 20.0]},
                },
            },
            "cut_groove": {
                "type": "cut_revolve",
                "dependencies": ["sketch_groove", "shaft_body"],
                "profile": "sketch_groove",
                "axis": "sketch_groove.cl",
                "angle": 360.0,
            },
        },
    }
    res = parse_part_graph(cast(JsonValue, doc))
    assert isinstance(res, PartGraph)

    sk = cast(SketchNode, res.nodes["sketch_shaft"])
    cl_ent = sk.entities["cl"]
    assert isinstance(cl_ent, Line)
    assert cl_ent.construction is True
    l1_ent = sk.entities["l1"]
    assert isinstance(l1_ent, Line)
    assert l1_ent.construction is False

    expected_angle: Final[float] = 360.0
    rev = cast(Revolve, res.nodes["shaft_body"])
    assert isinstance(rev, Revolve)
    assert rev.type == "revolve"
    assert rev.profile == "sketch_shaft"
    assert rev.axis == "sketch_shaft.cl"
    assert rev.angle == expected_angle
    assert rev.merge_result is True

    cut_rev = cast(CutRevolve, res.nodes["cut_groove"])
    assert isinstance(cut_rev, CutRevolve)
    assert cut_rev.type == "cut_revolve"
    assert cut_rev.profile == "sketch_groove"
    assert cut_rev.axis == "sketch_groove.cl"
    assert cut_rev.angle == expected_angle
