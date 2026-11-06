"""The authoring guide is generated from the real rules and its examples must be valid."""

import json
import re

import pytest
from cad_application.authoring_guide import EXAMPLES, build_guide
from cad_application.tools.list_feature_types import MVP_TYPES
from cad_compiler.validator.semantic import validate_graph
from cad_ir.part_feature_graph.model import PartGraph
from cad_ir.part_feature_graph.parse import parse_part_graph
from cad_ir.part_feature_graph.planes import plane_axes
from cad_verification.part import expected_geometry

PLANES = ("plane:front", "plane:top", "plane:right")


def test_guide_names_every_supported_node_type() -> None:
    guide = build_guide()
    for name, _ in MVP_TYPES:
        assert f"`{name}`" in guide


@pytest.mark.parametrize("plane", PLANES)
def test_guide_states_each_plane_axes_from_the_code(plane: str) -> None:
    guide = build_guide()
    axes = plane_axes(plane)
    assert f"`{plane}`" in guide
    assert str(axes.normal) in guide
    assert str(axes.x_axis) in guide
    assert str(axes.y_axis) in guide


def test_guide_tells_the_agent_to_refuse_unsupported_requests() -> None:
    guide = build_guide().lower()
    assert "cannot fulfil" in guide
    assert "do not approximate" in guide
    for unsupported in ("fillet", "chamfer", "arc", "pattern", "face"):
        assert unsupported in guide


def test_guide_states_the_workflow_order() -> None:
    guide = build_guide()
    assert guide.index("validate_part_graph") < guide.index("apply_part_graph")


def test_guide_is_deterministic() -> None:
    assert build_guide() == build_guide()


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_each_example_is_valid_and_embedded_in_the_guide(name: str) -> None:
    graph = parse_part_graph(EXAMPLES[name].graph)
    assert isinstance(graph, PartGraph), graph
    assert validate_graph(graph) == ()
    assert json.dumps(EXAMPLES[name].graph, indent=2) in build_guide()


def test_block_example_matches_its_stated_size() -> None:
    graph = parse_part_graph(EXAMPLES["block"].graph)
    assert isinstance(graph, PartGraph)
    box = expected_geometry(graph).bbox_mm
    assert (box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z) == (40, 30, 10)


def test_every_example_has_a_request_sentence() -> None:
    for example in EXAMPLES.values():
        assert re.search(r"\d", example.request)
