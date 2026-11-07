"""Tests for semantic rules and degenerate geometry rejection (spec 5.7, 6.7.2)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
from cad_compiler.validator.semantic import (
    _validate_lines_loop,  # pyright: ignore[reportPrivateUsage]
    validate_graph,
)
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph.model import (
    Arc,
    CenterRectangle,
    Circle,
    CircularPattern,
    CornerRectangle,
    CutRevolve,
    EndCondition,
    Line,
    LinearPattern,
    LinearPatternDirection,
    Mirror,
    PartGraph,
    Revolve,
    SketchNode,
    SolidNode,
    StraightSlot,
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


# --- cut profiles stay exactly computable (design section 5) ---


def _rect(x0: float, y0: float, x1: float, y1: float) -> dict[str, Line | Circle]:
    return {
        "a": Line(start=(x0, y0), end=(x1, y0)),
        "b": Line(start=(x1, y0), end=(x1, y1)),
        "c": Line(start=(x1, y1), end=(x0, y1)),
        "d": Line(start=(x0, y1), end=(x0, y0)),
    }


PLATE_PROFILE: Final[dict[str, Line | Circle]] = _rect(-50.0, -30.0, 50.0, 30.0)
DISC_PROFILE: Final[dict[str, Line | Circle]] = {"o": Circle(center=(0.0, 0.0), diameter=40.0)}


def _with_cuts(
    base_profile: dict[str, Line | Circle], *cut_profiles: dict[str, Line | Circle]
) -> PartGraph:
    """A base extrude plus one through cut per profile."""
    nodes: dict[str, SketchNode | SolidNode] = {
        "sketch_base": SketchNode(plane="plane:front", entities=base_profile),
        "extrude_base": SolidNode(
            type="extrude",
            profile="sketch_base",
            end_condition=EndCondition(type="blind", depth=10.0),
            dependencies=("sketch_base",),
        ),
    }
    for index, entities in enumerate(cut_profiles):
        nodes[f"sketch_cut{index}"] = SketchNode(plane="plane:front", entities=entities)
        nodes[f"cut{index}"] = SolidNode(
            type="cut_extrude",
            profile=f"sketch_cut{index}",
            end_condition=EndCondition(type="through_all_both"),
            dependencies=(f"sketch_cut{index}", "extrude_base"),
        )
    return PartGraph(id="cuts", schema_version="0.1", units="mm", origin="built", nodes=nodes)


def _circle(x: float, y: float, diameter: float) -> dict[str, Line | Circle]:
    return {"h": Circle(center=(x, y), diameter=diameter)}


@pytest.mark.parametrize(
    "graph",
    [
        pytest.param(_with_cuts(PLATE_PROFILE, _rect(10.0, 0.0, 30.0, 20.0)), id="loop_in_loop"),
        pytest.param(_with_cuts(DISC_PROFILE, _circle(5.0, 0.0, 10.0)), id="circle_in_circle"),
        pytest.param(_with_cuts(DISC_PROFILE, _rect(-5.0, -5.0, 5.0, 5.0)), id="loop_in_circle"),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _circle(-20.0, 0.0, 10.0), _circle(20.0, 0.0, 10.0)),
            id="separate_circles",
        ),
        pytest.param(
            _with_cuts(
                PLATE_PROFILE, _rect(-40.0, -10.0, -20.0, 10.0), _rect(20.0, -10.0, 40.0, 10.0)
            ),
            id="separate_loops",
        ),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _rect(-40.0, -10.0, -20.0, 10.0), _circle(20.0, 0.0, 10.0)),
            id="separate_loop_and_circle",
        ),
    ],
)
def test_exactly_computable_cuts_accepted(graph: PartGraph) -> None:
    assert validate_graph(graph) == ()


@pytest.mark.parametrize(
    "graph",
    [
        pytest.param(_with_cuts(DISC_PROFILE, _circle(100.0, 0.0, 4.0)), id="circle_outside_disc"),
        pytest.param(_with_cuts(DISC_PROFILE, _circle(15.0, 0.0, 12.0)), id="circle_crosses_disc"),
        pytest.param(_with_cuts(DISC_PROFILE, _circle(0.0, 0.0, 40.0)), id="circle_equals_disc"),
        pytest.param(_with_cuts(DISC_PROFILE, _rect(0.0, 0.0, 30.0, 5.0)), id="loop_crosses_disc"),
        pytest.param(_with_cuts(PLATE_PROFILE, _rect(40.0, 0.0, 60.0, 20.0)), id="loop_crosses"),
        pytest.param(_with_cuts(PLATE_PROFILE, _rect(60.0, 0.0, 80.0, 20.0)), id="loop_outside"),
        pytest.param(_with_cuts(PLATE_PROFILE, _rect(30.0, 0.0, 50.0, 20.0)), id="loop_touches"),
        pytest.param(_with_cuts(PLATE_PROFILE, PLATE_PROFILE), id="loop_equals_base"),
        pytest.param(_with_cuts(PLATE_PROFILE, _rect(-60.0, -40.0, 60.0, 40.0)), id="loop_around"),
    ],
)
def test_cut_not_strictly_inside_base_rejected(graph: PartGraph) -> None:
    assert any(i.code == ErrorCode.IR_RULE_VIOLATED for i in validate_graph(graph))


def test_cut_mixing_lines_and_circles_rejected() -> None:
    mixed: dict[str, Line | Circle] = {**_rect(10.0, 0.0, 30.0, 20.0), **_circle(-20.0, 0.0, 10.0)}
    issues = validate_graph(_with_cuts(PLATE_PROFILE, mixed))
    assert any(i.code == ErrorCode.IR_RULE_VIOLATED and "mix" in i.message for i in issues)


@pytest.mark.parametrize(
    "graph",
    [
        pytest.param(
            _with_cuts(PLATE_PROFILE, _circle(0.0, 0.0, 10.0), _circle(0.0, 0.0, 10.0)),
            id="same_hole_twice",
        ),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _circle(0.0, 0.0, 10.0), _circle(5.0, 0.0, 10.0)),
            id="circles_overlap",
        ),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _rect(-10.0, -10.0, 10.0, 10.0), _circle(0.0, 0.0, 4.0)),
            id="circle_inside_loop",
        ),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _rect(-2.0, -2.0, 2.0, 2.0), _circle(0.0, 0.0, 20.0)),
            id="loop_inside_circle",
        ),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _rect(-10.0, -10.0, 10.0, 10.0), _circle(10.0, 0.0, 6.0)),
            id="circle_crosses_loop",
        ),
        pytest.param(
            _with_cuts(
                PLATE_PROFILE, _rect(-10.0, -10.0, 10.0, 10.0), _rect(-10.0, -10.0, 10.0, 10.0)
            ),
            id="identical_loops",
        ),
        pytest.param(
            _with_cuts(
                PLATE_PROFILE, _rect(-20.0, -10.0, 0.0, 10.0), _rect(-10.0, -10.0, 10.0, 10.0)
            ),
            id="loops_share_an_edge_line",
        ),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _rect(-20.0, -20.0, 20.0, 20.0), _rect(-5.0, -5.0, 5.0, 5.0)),
            id="loop_inside_loop",
        ),
        pytest.param(
            _with_cuts(PLATE_PROFILE, _rect(-10.0, -5.0, 10.0, 5.0), _rect(-5.0, -10.0, 5.0, 10.0)),
            id="loops_cross",
        ),
    ],
)
def test_overlapping_cut_features_rejected(graph: PartGraph) -> None:
    issues = validate_graph(graph)
    assert any(i.code == ErrorCode.IR_RULE_VIOLATED and "overlap" in i.message for i in issues)


def test_two_cuts_sharing_one_sketch_rejected() -> None:
    base = _with_cuts(PLATE_PROFILE, _circle(0.0, 0.0, 10.0))
    nodes = dict(base.nodes)
    nodes["cut_again"] = SolidNode(
        type="cut_extrude",
        profile="sketch_cut0",
        end_condition=EndCondition(type="through_all_both"),
        dependencies=("sketch_cut0", "extrude_base"),
    )
    graph = PartGraph(
        id=base.id,
        schema_version=base.schema_version,
        units=base.units,
        origin=base.origin,
        nodes=nodes,
    )
    issues = validate_graph(graph)
    assert any(i.code == ErrorCode.IR_RULE_VIOLATED and "overlap" in i.message for i in issues)


def _square(x: float, y: float, size: float) -> list[Line]:
    a, b, c, d = (x, y), (x + size, y), (x + size, y + size), (x, y + size)
    return [Line(start=a, end=b), Line(start=b, end=c), Line(start=c, end=d), Line(start=d, end=a)]


def test_separate_line_loops_rejected() -> None:
    issues = _validate_lines_loop(_square(0, 0, 10) + _square(30, 0, 10), "/nodes/s")
    assert [i.code for i in issues] == [ErrorCode.IR_RULE_VIOLATED]


def test_single_line_loop_accepted() -> None:
    assert _validate_lines_loop(_square(0, 0, 10), "/nodes/s") == []


def test_valid_arc_in_sketch_loop() -> None:
    entities = {
        "l1": Line(start=(-20.0, -10.0), end=(20.0, -10.0)),
        "a1": Arc(center=(20.0, 0.0), start=(20.0, -10.0), end=(20.0, 10.0), direction="ccw"),
        "l2": Line(start=(20.0, 10.0), end=(-20.0, 10.0)),
        "a2": Arc(center=(-20.0, 0.0), start=(-20.0, 10.0), end=(-20.0, -10.0), direction="ccw"),
    }
    graph = PartGraph(
        id="slot_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert not issues


def test_arc_unequal_radius_rejected() -> None:
    entities = {
        "a1": Arc(center=(0.0, 0.0), start=(10.0, 0.0), end=(0.0, 12.0), direction="ccw"),
    }
    graph = PartGraph(
        id="bad_arc",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "radius" in i.message.lower() for i in issues
    )


def test_arc_coincident_start_end_rejected() -> None:
    entities = {
        "a1": Arc(center=(0.0, 0.0), start=(10.0, 0.0), end=(10.0, 0.0), direction="ccw"),
    }
    graph = PartGraph(
        id="coincident_arc",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED
        and ("coincident" in i.message.lower() or "circle" in i.message.lower())
        for i in issues
    )


def test_corner_rectangle_profile_valid() -> None:
    entities = {
        "r1": CornerRectangle(corner1=(-50.0, -30.0), corner2=(50.0, 30.0)),
    }
    graph = PartGraph(
        id="corner_rect_valid",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert not issues, [f"{i.pointer}: {i.message}" for i in issues]


def test_center_rectangle_profile_valid() -> None:
    entities = {
        "r1": CenterRectangle(center=(0.0, 0.0), width=100.0, height=60.0),
    }
    graph = PartGraph(
        id="center_rect_valid",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert not issues, [f"{i.pointer}: {i.message}" for i in issues]


def test_corner_rectangle_degenerate_rejected() -> None:
    entities = {
        "r1": CornerRectangle(corner1=(-50.0, -30.0), corner2=(-50.0, 30.0)),
    }
    graph = PartGraph(
        id="corner_rect_degen",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "rectangle" in i.message.lower() for i in issues
    )


def test_center_rectangle_degenerate_rejected() -> None:
    entities = {
        "r1": CenterRectangle(center=(0.0, 0.0), width=0.005, height=60.0),
    }
    graph = PartGraph(
        id="center_rect_degen",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "rectangle" in i.message.lower() for i in issues
    )


def test_straight_slot_profile_valid() -> None:
    entities = {
        "s1": StraightSlot(start_point=(-20.0, 0.0), end_point=(20.0, 0.0), width=10.0),
    }
    graph = PartGraph(
        id="straight_slot_valid",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert not issues, [f"{i.pointer}: {i.message}" for i in issues]


def test_straight_slot_zero_length_rejected() -> None:
    entities = {
        "s1": StraightSlot(start_point=(10.0, 10.0), end_point=(10.0, 10.0), width=10.0),
    }
    graph = PartGraph(
        id="straight_slot_degen_len",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert any(i.code == ErrorCode.IR_RULE_VIOLATED and "slot" in i.message.lower() for i in issues)


def test_straight_slot_too_narrow_rejected() -> None:
    entities = {
        "s1": StraightSlot(start_point=(0.0, 0.0), end_point=(20.0, 0.0), width=0.005),
    }
    graph = PartGraph(
        id="straight_slot_degen_w",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert any(i.code == ErrorCode.IR_RULE_VIOLATED and "slot" in i.message.lower() for i in issues)


def test_straight_slot_mixed_profile_rejected() -> None:
    entities: dict[str, Any] = {
        "s1": StraightSlot(start_point=(-20.0, 0.0), end_point=(20.0, 0.0), width=10.0),
        "c1": Circle(center=(0.0, 0.0), diameter=5.0),
    }
    graph = PartGraph(
        id="straight_slot_mixed",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(plane="plane:front", entities=entities),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "cannot mix" in i.message.lower() for i in issues
    )


def _pattern_base_graph(
    *,
    hole: tuple[float, float, float] = (-30.0, 0.0, 10.0),
    spacing: float = 20.0,
    count: int = 4,
    seeds: tuple[str, ...] = ("cut_hole",),
    pattern_deps: tuple[str, ...] = ("cut_hole", "extrude_base"),
) -> PartGraph:
    return PartGraph(
        id="pattern_graph",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={"r1": CenterRectangle(center=(0.0, 0.0), width=100.0, height=60.0)},
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_hole": SketchNode(
                plane="plane:front",
                entities={"c1": Circle(center=(hole[0], hole[1]), diameter=hole[2])},
            ),
            "cut_hole": SolidNode(
                type="cut_extrude",
                profile="sketch_hole",
                end_condition=EndCondition(type="through_all_both"),
                dependencies=("sketch_hole", "extrude_base"),
            ),
            "pattern_holes": LinearPattern(
                seeds=seeds,
                direction_1=LinearPatternDirection(
                    direction="plane:right",
                    spacing=spacing,
                    count=count,
                ),
                dependencies=pattern_deps,
            ),
        },
    )


def test_linear_pattern_accepted() -> None:
    graph = _pattern_base_graph()
    assert validate_graph(graph) == ()


def test_linear_pattern_unresolved_seed_rejected() -> None:
    graph = _pattern_base_graph(
        seeds=("missing_cut",), pattern_deps=("missing_cut", "extrude_base")
    )
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_REFERENCE_UNRESOLVED and "missing_cut" in i.message for i in issues
    )


def test_linear_pattern_non_cut_seed_rejected() -> None:
    graph = _pattern_base_graph(seeds=("extrude_base",), pattern_deps=("extrude_base",))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "must be a cut feature" in i.message
        for i in issues
    )


def test_linear_pattern_missing_dependency_rejected() -> None:
    graph = _pattern_base_graph(pattern_deps=("extrude_base",))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "must depend on seed" in i.message for i in issues
    )


def test_linear_pattern_instances_outside_base_rejected() -> None:
    # Base width 100 (-50 to +50). Hole center 0.0, count 4, spacing 20 -> centers 0, 20, 40, 60.
    # At center 60, radius 5, right edge is 65 > 50 -> outside base!
    graph = _pattern_base_graph(hole=(0.0, 0.0, 10.0), count=4, spacing=20.0)
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "outside" in i.message.lower() for i in issues
    )


def test_linear_pattern_spacing_too_small_rejected() -> None:
    # Hole diameter 10, spacing 8 -> instances overlap
    graph = _pattern_base_graph(hole=(-30.0, 0.0, 10.0), spacing=8.0, count=2)
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "overlap" in i.message.lower() for i in issues
    )


def _circular_pattern_base_graph(  # noqa: PLR0913
    *,
    hole: tuple[float, float, float] = (35.0, 0.0, 8.0),
    spacing: float = 360.0,
    count: int = 6,
    equal_spacing: bool = True,
    seeds: tuple[str, ...] = ("cut_hole",),
    pattern_deps: tuple[str, ...] = ("cut_hole", "extrude_base"),
    axis: str = "plane:front",
) -> PartGraph:
    return PartGraph(
        id="circular_pattern_graph",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={"c1": Circle(center=(0.0, 0.0), diameter=100.0)},
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_hole": SketchNode(
                plane="plane:front",
                entities={"c2": Circle(center=(hole[0], hole[1]), diameter=hole[2])},
            ),
            "cut_hole": SolidNode(
                type="cut_extrude",
                profile="sketch_hole",
                end_condition=EndCondition(type="through_all_both"),
                dependencies=("sketch_hole", "extrude_base"),
            ),
            "pattern_holes": CircularPattern(
                seeds=seeds,
                axis=axis,
                count=count,
                spacing=spacing,
                equal_spacing=equal_spacing,
                dependencies=pattern_deps,
            ),
        },
    )


def test_circular_pattern_accepted() -> None:
    graph = _circular_pattern_base_graph()
    assert validate_graph(graph) == ()


def test_circular_pattern_unresolved_seed_rejected() -> None:
    graph = _circular_pattern_base_graph(
        seeds=("missing_cut",), pattern_deps=("missing_cut", "extrude_base")
    )
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_REFERENCE_UNRESOLVED and "missing_cut" in i.message for i in issues
    )


def test_circular_pattern_non_cut_seed_rejected() -> None:
    graph = _circular_pattern_base_graph(seeds=("extrude_base",), pattern_deps=("extrude_base",))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "must be a cut feature" in i.message
        for i in issues
    )


def test_circular_pattern_missing_dependency_rejected() -> None:
    graph = _circular_pattern_base_graph(pattern_deps=("extrude_base",))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "must depend on seed" in i.message for i in issues
    )


def test_circular_pattern_spacing_out_of_bounds_rejected() -> None:
    graph = _circular_pattern_base_graph(spacing=400.0)
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "spacing" in i.message.lower() for i in issues
    )


def _mirror_base_graph(
    *,
    hole: tuple[float, float, float] = (25.0, 0.0, 10.0),
    plane: str = "plane:right",
    merge: bool = True,
    seeds: tuple[str, ...] = ("cut_hole",),
    mirror_deps: tuple[str, ...] = ("cut_hole", "extrude_base"),
) -> PartGraph:
    return PartGraph(
        id="mirror_graph",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={
                    "l1": Line(start=(-50.0, -25.0), end=(50.0, -25.0)),
                    "l2": Line(start=(50.0, -25.0), end=(50.0, 25.0)),
                    "l3": Line(start=(50.0, 25.0), end=(-50.0, 25.0)),
                    "l4": Line(start=(-50.0, 25.0), end=(-50.0, -25.0)),
                },
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_hole": SketchNode(
                plane="plane:front",
                entities={"c1": Circle(center=(hole[0], hole[1]), diameter=hole[2])},
            ),
            "cut_hole": SolidNode(
                type="cut_extrude",
                profile="sketch_hole",
                end_condition=EndCondition(type="through_all_both"),
                dependencies=("sketch_hole", "extrude_base"),
            ),
            "mirror_hole": Mirror(
                seeds=seeds,
                plane=plane,
                merge=merge,
                dependencies=mirror_deps,
            ),
        },
    )


def test_mirror_accepted() -> None:
    graph = _mirror_base_graph()
    assert validate_graph(graph) == ()


def test_mirror_unresolved_seed_rejected() -> None:
    graph = _mirror_base_graph(seeds=("missing_cut",), mirror_deps=("missing_cut", "extrude_base"))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_REFERENCE_UNRESOLVED and "missing_cut" in i.message for i in issues
    )


def test_mirror_non_solid_seed_rejected() -> None:
    graph = _mirror_base_graph(seeds=("sketch_base",), mirror_deps=("sketch_base", "extrude_base"))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "must be a solid or pattern feature" in i.message
        for i in issues
    )


def test_mirror_missing_dependency_rejected() -> None:
    graph = _mirror_base_graph(mirror_deps=("extrude_base",))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "must depend on seed" in i.message for i in issues
    )


def _revolve_base_graph(
    *,
    angle: float = 360.0,
    profile: str = "sketch_shaft",
    revolve_deps: tuple[str, ...] = ("sketch_shaft",),
    include_cut: bool = False,
    cut_deps: tuple[str, ...] = ("sketch_groove", "shaft_body"),
) -> PartGraph:
    nodes: dict[str, Any] = {
        "sketch_shaft": SketchNode(
            plane="plane:front",
            entities={
                "cl": Line(start=(0.0, 0.0), end=(0.0, 50.0), construction=True),
                "l1": Line(start=(0.0, 0.0), end=(15.0, 0.0)),
                "l2": Line(start=(15.0, 0.0), end=(15.0, 50.0)),
                "l3": Line(start=(15.0, 50.0), end=(0.0, 50.0)),
                "l4": Line(start=(0.0, 50.0), end=(0.0, 0.0)),
            },
        ),
        "shaft_body": Revolve(
            profile=profile,
            axis="sketch_shaft.cl",
            angle=angle,
            dependencies=revolve_deps,
        ),
    }
    if include_cut:
        nodes["sketch_groove"] = SketchNode(
            plane="plane:front",
            entities={
                "cl": Line(start=(0.0, 0.0), end=(0.0, 50.0), construction=True),
                "g1": Line(start=(12.0, 20.0), end=(15.0, 20.0)),
                "g2": Line(start=(15.0, 20.0), end=(15.0, 25.0)),
                "g3": Line(start=(15.0, 25.0), end=(12.0, 25.0)),
                "g4": Line(start=(12.0, 25.0), end=(12.0, 20.0)),
            },
        )
        nodes["cut_groove"] = CutRevolve(
            profile="sketch_groove",
            axis="sketch_groove.cl",
            angle=360.0,
            dependencies=cut_deps,
        )
    return PartGraph(
        id="turned_shaft",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes=nodes,
    )


def test_revolve_accepted() -> None:
    graph = _revolve_base_graph(include_cut=True)
    assert validate_graph(graph) == ()


def test_revolve_profile_not_sketch_rejected() -> None:
    graph = _revolve_base_graph(profile="missing_sketch", revolve_deps=("missing_sketch",))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_REFERENCE_UNRESOLVED and "missing_sketch" in i.message
        for i in issues
    )


def test_revolve_invalid_angle_rejected() -> None:
    graph = _revolve_base_graph(angle=0.0)
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED and "angle must be" in i.message for i in issues
    )


def test_cut_revolve_without_prior_solid_rejected() -> None:
    # A cut_revolve that doesn't depend on any solid body
    graph = _revolve_base_graph(include_cut=True, cut_deps=("sketch_groove",))
    issues = validate_graph(graph)
    assert any(
        i.code == ErrorCode.IR_RULE_VIOLATED
        and "must depend on at least one prior solid" in i.message
        for i in issues
    )
