"""Validation of sketches placed on an extrude's cap face (ADR-070)."""

import copy
from collections.abc import Sequence
from typing import Any

from cad_compiler.validator.semantic import validate_graph
from cad_ir.part_feature_graph.model import PartGraph
from cad_ir.part_feature_graph.parse import parse_part_graph

L_OUTLINE: list[tuple[float, float]] = [(0, 0), (60, 0), (60, 20), (20, 20), (20, 40), (0, 40)]


def _lines(points: Sequence[tuple[float, float]]) -> dict[str, Any]:
    n = len(points)
    return {
        f"l{i + 1}": {"type": "line", "start": list(points[i]), "end": list(points[(i + 1) % n])}
        for i in range(n)
    }


def _graph(
    plane: str = "extrude_base.end_face",
    center: tuple[float, float] = (0.0, 0.0),
    outline: Sequence[tuple[float, float]] | None = None,
    base_plane: str = "plane:front",
) -> dict[str, Any]:
    box = [(-20, -15), (20, -15), (20, 15), (-20, 15)]
    return {
        "module": "part",
        "id": "face_hole",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": base_plane,
                "entities": _lines(outline or box),
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10},
            },
            "sketch_hole": {
                "type": "sketch",
                "plane": plane,
                "dependencies": ["extrude_base"],
                "entities": {"c1": {"type": "circle", "center": list(center), "diameter": 5}},
            },
            "cut_hole": {
                "type": "cut_extrude",
                "dependencies": ["sketch_hole", "extrude_base"],
                "profile": "sketch_hole",
                "end_condition": {"type": "blind", "depth": 4},
            },
        },
    }


def _messages(raw: dict[str, Any]) -> str:
    graph = parse_part_graph(copy.deepcopy(raw))
    assert isinstance(graph, PartGraph), graph
    return " | ".join(issue.message for issue in validate_graph(graph))


def test_a_hole_on_the_end_face_is_valid() -> None:
    assert _messages(_graph()) == ""


def test_a_hole_on_the_start_face_is_valid() -> None:
    assert _messages(_graph(plane="extrude_base.start_face")) == ""


def test_only_the_cap_faces_are_supported() -> None:
    assert "start_face or end_face" in _messages(_graph(plane="extrude_base.side_faces"))


def test_the_referenced_node_must_exist() -> None:
    assert "not found" in _messages(_graph(plane="nope.end_face"))


def test_the_referenced_node_must_be_the_extrude() -> None:
    raw = _graph(plane="sketch_base.end_face")
    assert "must be the extrude" in _messages(raw)


def test_the_sketch_must_list_the_extrude_as_a_dependency() -> None:
    raw = _graph()
    raw["nodes"]["sketch_hole"]["dependencies"] = []
    assert "add the extrude to its dependencies" in _messages(raw)


def test_a_start_face_sketch_is_checked_in_the_base_frame() -> None:
    # The arm of the L is x 0..20, y 20..40. On a start face, sketch x is mirrored.
    for base_plane in ("plane:front", "plane:top", "plane:right"):
        assert _messages(_graph("extrude_base.end_face", (10, 30), L_OUTLINE, base_plane)) == ""
        assert _messages(_graph("extrude_base.start_face", (-10, 30), L_OUTLINE, base_plane)) == ""
        assert "inside" in _messages(
            _graph("extrude_base.start_face", (10, 30), L_OUTLINE, base_plane)
        )
