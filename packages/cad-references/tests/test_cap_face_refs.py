"""Parameterized tests for semantic cap-face reference resolution across all 6 datum/cap combos."""

from typing import Any

import pytest
from cad_ir.part_feature_graph import PartGraph, parse_part_graph
from cad_references.semantic import resolve_cap_face_signature


def _graph(base_plane: str, cap_role: str) -> PartGraph:
    box = [(-20, -15), (20, -15), (20, 15), (-20, 15)]
    raw: dict[str, Any] = {
        "module": "part",
        "id": "block_cap",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": base_plane,
                "entities": {
                    f"l{i + 1}": {
                        "type": "line",
                        "start": list(box[i]),
                        "end": list(box[(i + 1) % 4]),
                    }
                    for i in range(4)
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10},
            },
            "sketch_hole": {
                "type": "sketch",
                "plane": f"extrude_base.{cap_role}",
                "dependencies": ["extrude_base"],
                "entities": {"c1": {"type": "circle", "center": [5, 0], "diameter": 6}},
            },
            "cut_hole": {
                "type": "cut_extrude",
                "dependencies": ["sketch_hole", "extrude_base"],
                "profile": "sketch_hole",
                "end_condition": {"type": "blind", "depth": 4},
            },
        },
    }
    parsed = parse_part_graph(raw)
    assert isinstance(parsed, PartGraph)
    return parsed


@pytest.mark.parametrize(
    ("base_plane", "role", "exp_normal", "exp_offset", "exp_axes"),
    [
        (
            "plane:front",
            "end_face",
            [0.0, 0.0, 1.0],
            10.0,
            ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]),
        ),
        (
            "plane:front",
            "start_face",
            [0.0, 0.0, -1.0],
            0.0,
            ([-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]),
        ),
        (
            "plane:top",
            "end_face",
            [0.0, 1.0, 0.0],
            10.0,
            ([1.0, 0.0, 0.0], [0.0, 0.0, -1.0]),
        ),
        (
            "plane:top",
            "start_face",
            [0.0, -1.0, 0.0],
            0.0,
            ([-1.0, 0.0, 0.0], [0.0, 0.0, -1.0]),
        ),
        (
            "plane:right",
            "end_face",
            [1.0, 0.0, 0.0],
            10.0,
            ([0.0, 0.0, -1.0], [0.0, 1.0, 0.0]),
        ),
        (
            "plane:right",
            "start_face",
            [-1.0, 0.0, 0.0],
            0.0,
            ([0.0, 0.0, 1.0], [0.0, 1.0, 0.0]),
        ),
    ],
)
def test_resolve_cap_face_signature_all_six_combinations(
    base_plane: str,
    role: str,
    exp_normal: list[float],
    exp_offset: float,
    exp_axes: tuple[list[float], list[float]],
) -> None:
    graph = _graph(base_plane, role)
    sig = resolve_cap_face_signature(graph, f"extrude_base.{role}")
    assert sig == {
        "feature": "extrude_base",
        "role": role,
        "normal": exp_normal,
        "offset_mm": exp_offset,
        "x_axis": exp_axes[0],
        "y_axis": exp_axes[1],
    }


def test_resolve_cap_face_signature_returns_none_for_standard_plane() -> None:
    graph = _graph("plane:front", "end_face")
    assert resolve_cap_face_signature(graph, "plane:front") is None
