"""Tests for topological build order and cycle rejection (spec 5.7.1, 6.7.2)."""

import json
from pathlib import Path
from typing import Any

from cad_compiler.graph.analyze import build_order
from cad_compiler.validator.semantic import validate_graph
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph.model import EndCondition, PartGraph, SketchNode, SolidNode
from cad_ir.part_feature_graph.parse import parse_part_graph

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas" / "part-feature-graph" / "valid"
PLATE_FIXTURE = FIXTURE_DIR / "plate_4h.json"


def _load_plate_graph() -> PartGraph:
    raw: dict[str, Any] = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
    res = parse_part_graph(raw)
    assert isinstance(res, PartGraph)
    return res


def test_build_order_plate() -> None:
    graph = _load_plate_graph()
    order = build_order(graph)
    assert order == ("sketch_base", "extrude_base", "sketch_holes", "cut_holes")


def test_cycle_rejected() -> None:
    # Graph with cycle: node_a -> node_b -> node_a
    nodes: dict[str, SketchNode | SolidNode] = {
        "sketch_a": SketchNode(
            plane="plane:front",
            entities={},
            dependencies=("cut_b",),
        ),
        "cut_b": SolidNode(
            type="cut_extrude",
            profile="sketch_a",
            end_condition=EndCondition(type="through_all_both"),
            dependencies=("sketch_a",),
        ),
    }
    graph = PartGraph(
        id="cycle_graph",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes=nodes,
    )
    issues = validate_graph(graph)
    assert any(issue.code == ErrorCode.IR_CYCLE for issue in issues)
