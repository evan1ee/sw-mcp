"""Tests for semantic rules and degenerate geometry rejection (spec 5.7, 6.7.2)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
from cad_compiler.validator.semantic import validate_graph
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph.model import (
    Circle,
    EndCondition,
    Line,
    PartGraph,
    SketchNode,
    SolidNode,
)
from cad_ir.part_feature_graph.parse import parse_part_graph

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas" / "part-feature-graph" / "valid"
PLATE_FIXTURE = FIXTURE_DIR / "plate_4h.json"
MIN_TWO_ERRORS: Final[int] = 2


def _plate_graph() -> PartGraph:
    raw: dict[str, Any] = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
    res = parse_part_graph(raw)
    assert isinstance(res, PartGraph)
    return res


def _make_open_loop(base: PartGraph) -> PartGraph:
    sketch = base.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    new_entities = dict(sketch.entities)
    new_entities["l4"] = Line(start=(-50.0, 30.0), end=(-40.0, -30.0))
    new_nodes = dict(base.nodes)
    new_nodes["sketch_base"] = SketchNode(
        plane=sketch.plane,
        entities=new_entities,
        dependencies=sketch.dependencies,
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_self_intersecting(base: PartGraph) -> PartGraph:
    sketch = base.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    new_entities = {
        "l1": Line(start=(-50.0, -30.0), end=(50.0, 30.0)),
        "l2": Line(start=(50.0, 30.0), end=(50.0, -30.0)),
        "l3": Line(start=(50.0, -30.0), end=(-50.0, 30.0)),
        "l4": Line(start=(-50.0, 30.0), end=(-50.0, -30.0)),
    }
    new_nodes = dict(base.nodes)
    new_nodes["sketch_base"] = SketchNode(
        plane=sketch.plane,
        entities=new_entities,
        dependencies=sketch.dependencies,
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_overlapping_circles(base: PartGraph) -> PartGraph:
    sketch = base.nodes["sketch_holes"]
    assert isinstance(sketch, SketchNode)
    new_entities = {
        "c1": Circle(center=(0.0, 0.0), diameter=8.0),
        "c2": Circle(center=(4.0, 0.0), diameter=8.0),
    }
    new_nodes = dict(base.nodes)
    new_nodes["sketch_holes"] = SketchNode(
        plane=sketch.plane,
        entities=new_entities,
        dependencies=sketch.dependencies,
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_hole_outside_profile(base: PartGraph) -> PartGraph:
    sketch = base.nodes["sketch_holes"]
    assert isinstance(sketch, SketchNode)
    new_entities = {
        "c1": Circle(center=(100.0, 100.0), diameter=8.0),
    }
    new_nodes = dict(base.nodes)
    new_nodes["sketch_holes"] = SketchNode(
        plane=sketch.plane,
        entities=new_entities,
        dependencies=sketch.dependencies,
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_hole_on_different_plane(base: PartGraph) -> PartGraph:
    sketch = base.nodes["sketch_holes"]
    assert isinstance(sketch, SketchNode)
    new_nodes = dict(base.nodes)
    new_nodes["sketch_holes"] = SketchNode(
        plane="plane:top",
        entities=sketch.entities,
        dependencies=sketch.dependencies,
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_two_extrudes(base: PartGraph) -> PartGraph:
    new_nodes = dict(base.nodes)
    new_nodes["extrude_second"] = SolidNode(
        type="extrude",
        profile="sketch_base",
        end_condition=EndCondition(type="blind", depth=5.0),
        dependencies=("sketch_base",),
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_several_circles_extrude(base: PartGraph) -> PartGraph:
    new_nodes = dict(base.nodes)
    new_nodes["sketch_base"] = SketchNode(
        plane="plane:front",
        entities={
            "c1": Circle(center=(0.0, 0.0), diameter=20.0),
            "c2": Circle(center=(30.0, 0.0), diameter=20.0),
        },
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_cut_before_extrude(base: PartGraph) -> PartGraph:
    cut = base.nodes["cut_holes"]
    assert isinstance(cut, SolidNode)
    new_nodes = dict(base.nodes)
    new_nodes["cut_holes"] = SolidNode(
        type=cut.type,
        profile=cut.profile,
        end_condition=cut.end_condition,
        dependencies=("sketch_holes",),
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_units_in(base: PartGraph) -> PartGraph:
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units="in",
        origin=base.origin,
        nodes=base.nodes,
    )


def _make_missing_profile(base: PartGraph) -> PartGraph:
    solid = base.nodes["extrude_base"]
    assert isinstance(solid, SolidNode)
    new_nodes = dict(base.nodes)
    new_nodes["extrude_base"] = SolidNode(
        type=solid.type,
        profile="sketch_missing",
        end_condition=solid.end_condition,
        dependencies=solid.dependencies,
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_profile_not_sketch(base: PartGraph) -> PartGraph:
    cut = base.nodes["cut_holes"]
    assert isinstance(cut, SolidNode)
    new_nodes = dict(base.nodes)
    new_nodes["cut_holes"] = SolidNode(
        type=cut.type,
        profile="extrude_base",
        end_condition=cut.end_condition,
        dependencies=cut.dependencies,
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=new_nodes,
    )


def _make_zero_length_line(base: PartGraph) -> PartGraph:
    nodes = dict(base.nodes)
    nodes["sketch_base"] = SketchNode(
        plane="plane:front",
        entities={
            "l1": Line(start=(0.0, 0.0), end=(0.0, 0.0)),
            "l2": Line(start=(0.0, 0.0), end=(10.0, 0.0)),
            "l3": Line(start=(10.0, 0.0), end=(0.0, 0.0)),
        },
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=nodes,
    )


def _make_small_diameter(base: PartGraph) -> PartGraph:
    nodes = dict(base.nodes)
    nodes["sketch_holes"] = SketchNode(
        plane="plane:front",
        entities={
            "c1": Circle(center=(0.0, 0.0), diameter=0.005),
        },
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=nodes,
    )


def _make_imperfect_loop(base: PartGraph) -> PartGraph:
    nodes = dict(base.nodes)
    nodes["sketch_base"] = SketchNode(
        plane="plane:front",
        entities={
            "l1": Line(start=(-50.0, -30.0), end=(50.0, -30.0)),
            "l2": Line(start=(50.0, -30.0), end=(50.0, 30.0)),
            "l3": Line(start=(50.0, 30.0), end=(-50.0, 30.0)),
            "l4": Line(start=(-50.0, 30.0), end=(-50.0 + 2e-6, -30.0)),
        },
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=nodes,
    )


def _make_tangent_hole(base: PartGraph) -> PartGraph:
    nodes = dict(base.nodes)
    nodes["sketch_holes"] = SketchNode(
        plane="plane:front",
        entities={
            "c1": Circle(center=(-46.0, 0.0), diameter=8.0),
        },
    )
    return PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=nodes,
    )


@pytest.mark.parametrize(
    ("rule_name", "mutator", "expected_code", "pointer_prefix"),
    [
        ("open loop", _make_open_loop, ErrorCode.IR_RULE_VIOLATED, "/nodes/sketch_base"),
        (
            "self-intersecting loop",
            _make_self_intersecting,
            ErrorCode.IR_RULE_VIOLATED,
            "/nodes/sketch_base",
        ),
        (
            "overlapping circles",
            _make_overlapping_circles,
            ErrorCode.IR_RULE_VIOLATED,
            "/nodes/sketch_holes",
        ),
        (
            "hole outside profile",
            _make_hole_outside_profile,
            ErrorCode.IR_RULE_VIOLATED,
            "/nodes/sketch_holes",
        ),
        (
            "hole different plane",
            _make_hole_on_different_plane,
            ErrorCode.IR_RULE_VIOLATED,
            "/nodes/sketch_holes",
        ),
        ("two extrudes", _make_two_extrudes, ErrorCode.IR_RULE_VIOLATED, "/nodes/extrude_second"),
        (
            "several circles extrude",
            _make_several_circles_extrude,
            ErrorCode.IR_RULE_VIOLATED,
            "/nodes/extrude_base",
        ),
        (
            "cut before extrude",
            _make_cut_before_extrude,
            ErrorCode.IR_RULE_VIOLATED,
            "/nodes/cut_holes",
        ),
        ("units: in", _make_units_in, ErrorCode.IR_RULE_VIOLATED, "/units"),
        (
            "missing profile",
            _make_missing_profile,
            ErrorCode.IR_REFERENCE_UNRESOLVED,
            "/nodes/extrude_base/profile",
        ),
        (
            "profile not sketch",
            _make_profile_not_sketch,
            ErrorCode.IR_RULE_VIOLATED,
            "/nodes/cut_holes/profile",
        ),
    ],
)
def test_rules(
    rule_name: str,
    mutator: Callable[[PartGraph], PartGraph],
    expected_code: ErrorCode,
    pointer_prefix: str,
) -> None:
    base = _plate_graph()
    broken = mutator(base)
    issues = validate_graph(broken)
    matching = [
        i for i in issues if i.code == expected_code and i.pointer.startswith(pointer_prefix)
    ]
    assert matching, f"Rule {rule_name} failed. Got: {issues}"


def test_two_errors_both_reported() -> None:
    base = _plate_graph()
    g1 = _make_units_in(base)
    g2 = _make_missing_profile(g1)
    issues = validate_graph(g2)
    codes = {i.code for i in issues}
    assert ErrorCode.IR_RULE_VIOLATED in codes
    assert ErrorCode.IR_REFERENCE_UNRESOLVED in codes
    assert len(issues) >= MIN_TWO_ERRORS


@pytest.mark.parametrize(
    ("case_name", "graph_mutator", "pointer_prefix"),
    [
        ("zero-length line", _make_zero_length_line, "/nodes/sketch_base/entities/l1"),
        ("diameter below 0.01 mm", _make_small_diameter, "/nodes/sketch_holes/entities/c1"),
        (
            "loop whose ends miss by more than quantum",
            _make_imperfect_loop,
            "/nodes/sketch_base/entities",
        ),
        ("hole tangent to the edge", _make_tangent_hole, "/nodes/sketch_holes/entities/c1"),
    ],
)
def test_degenerate_rejected(
    case_name: str,
    graph_mutator: Callable[[PartGraph], PartGraph],
    pointer_prefix: str,
) -> None:
    base = _plate_graph()
    g = graph_mutator(base)
    issues = validate_graph(g)
    matching = [
        i
        for i in issues
        if i.code == ErrorCode.IR_RULE_VIOLATED and i.pointer.startswith(pointer_prefix)
    ]
    assert matching, f"Degenerate case {case_name} was not rejected. Got: {issues}"


def test_unordered_sketch_lines() -> None:
    base = _plate_graph()
    sketch = base.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    shuffled_entities = {
        "l3": Line(start=(50.0, -30.0), end=(50.0, 30.0)),
        "l1": Line(start=(50.0, 30.0), end=(-50.0, 30.0)),
        "l4": Line(start=(-50.0, 30.0), end=(-50.0, -30.0)),
        "l2": Line(start=(-50.0, -30.0), end=(50.0, -30.0)),
    }
    nodes = dict(base.nodes)
    nodes["sketch_base"] = SketchNode(
        plane=sketch.plane,
        entities=shuffled_entities,
        dependencies=sketch.dependencies,
    )
    g = PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=nodes,
    )
    issues = validate_graph(g)
    assert issues == (), f"Expected zero issues with unordered lines, got {issues}"


def test_unordered_sketch_lines_rejects_hole_outside() -> None:
    base = _plate_graph()
    sketch = base.nodes["sketch_base"]
    assert isinstance(sketch, SketchNode)
    shuffled_entities = {
        "l3": Line(start=(50.0, -30.0), end=(50.0, 30.0)),
        "l1": Line(start=(50.0, 30.0), end=(-50.0, 30.0)),
        "l4": Line(start=(-50.0, 30.0), end=(-50.0, -30.0)),
        "l2": Line(start=(-50.0, -30.0), end=(50.0, -30.0)),
    }
    nodes = dict(base.nodes)
    nodes["sketch_base"] = SketchNode(
        plane=sketch.plane,
        entities=shuffled_entities,
        dependencies=sketch.dependencies,
    )
    nodes["sketch_holes"] = SketchNode(
        plane="plane:front",
        entities={"c1": Circle(center=(100.0, 100.0), diameter=8.0)},
        dependencies=base.nodes["sketch_holes"].dependencies,
    )
    g = PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=nodes,
    )
    issues = validate_graph(g)
    assert any(i.code == ErrorCode.IR_RULE_VIOLATED and "outside" in i.message for i in issues)
