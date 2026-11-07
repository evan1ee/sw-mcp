"""Known-good answers for every case, used to test the checker and as a baseline."""

from typing import Any

Point = tuple[float, float]


def _lines(points: list[Point]) -> dict[str, Any]:
    count = len(points)
    return {
        f"l{i + 1}": {
            "type": "line",
            "start": list(points[i]),
            "end": list(points[(i + 1) % count]),
        }
        for i in range(count)
    }


def _circles(circles: list[tuple[float, float, float]]) -> dict[str, Any]:
    return {
        f"c{i + 1}": {"type": "circle", "center": [x, y], "diameter": d}
        for i, (x, y, d) in enumerate(circles)
    }


def _rect(width: float, height: float) -> list[Point]:
    x, y = width / 2, height / 2
    return [(-x, -y), (x, -y), (x, y), (-x, y)]


def _slot(length: float, width: float) -> dict[str, Any]:
    half_l = (length - width) / 2.0
    return {
        "s1": {
            "type": "straight_slot",
            "start_point": [-half_l, 0.0],
            "end_point": [half_l, 0.0],
            "width": width,
        }
    }


def part(
    graph_id: str,
    base_entities: dict[str, Any],
    depth: float,
    holes: list[tuple[float, float, float]] | None = None,
) -> dict[str, Any]:
    """Build a one-extrude part with optional through holes, all on ``plane:front``."""
    nodes: dict[str, Any] = {
        "sketch_base": {"type": "sketch", "plane": "plane:front", "entities": base_entities},
        "extrude_base": {
            "type": "extrude",
            "dependencies": ["sketch_base"],
            "profile": "sketch_base",
            "end_condition": {"type": "blind", "depth": depth},
        },
    }
    if holes:
        nodes["sketch_holes"] = {
            "type": "sketch",
            "plane": "plane:front",
            "entities": _circles(holes),
        }
        nodes["cut_holes"] = {
            "type": "cut_extrude",
            "dependencies": ["sketch_holes", "extrude_base"],
            "profile": "sketch_holes",
            "end_condition": {"type": "through_all_both"},
        }
    return {
        "module": "part",
        "id": graph_id,
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": nodes,
    }


def _top_face_hole() -> dict[str, Any]:
    """A 40 x 30 x 10 block with a Ø5 x 4 hole in the middle of the end face."""
    graph = part("block_top_hole", _lines(_rect(40, 30)), 10, [(0, 0, 5)])
    graph["nodes"]["sketch_holes"]["plane"] = "extrude_base.end_face"
    graph["nodes"]["sketch_holes"]["dependencies"] = ["extrude_base"]
    graph["nodes"]["cut_holes"]["end_condition"] = {"type": "blind", "depth": 4}
    return graph


def _start_face_hole() -> dict[str, Any]:
    """A 40 x 30 x 10 block with a Ø5 x 4 hole in the middle of the start face."""
    graph = part("block_start_hole", _lines(_rect(40, 30)), 10, [(0, 0, 5)])
    graph["nodes"]["sketch_holes"]["plane"] = "extrude_base.start_face"
    graph["nodes"]["sketch_holes"]["dependencies"] = ["extrude_base"]
    graph["nodes"]["cut_holes"]["end_condition"] = {"type": "blind", "depth": 4}
    return graph


L_SHAPE: list[Point] = [(0, 0), (60, 0), (60, 20), (20, 20), (20, 40), (0, 40)]


def _rectangles_plate() -> dict[str, Any]:
    return {
        "module": "part",
        "id": "plate_rectangles",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "base_rect": {
                        "type": "center_rectangle",
                        "center": [0.0, 0.0],
                        "width": 80.0,
                        "height": 50.0,
                    }
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10.0},
            },
            "sketch_cut": {
                "type": "sketch",
                "plane": "plane:front",
                "entities": {
                    "cut_rect": {
                        "type": "center_rectangle",
                        "center": [0.0, 0.0],
                        "width": 30.0,
                        "height": 20.0,
                    }
                },
            },
            "cut_rect": {
                "type": "cut_extrude",
                "dependencies": ["sketch_cut", "extrude_base"],
                "profile": "sketch_cut",
                "end_condition": {"type": "through_all_both"},
            },
        },
    }


# A None answer is a refusal.
REFERENCE_ANSWERS: dict[str, dict[str, Any] | None] = {
    "block": part("block", _lines(_rect(40, 30)), 10),
    "block_centre_hole": part("block_hole", _lines(_rect(40, 30)), 10, [(0, 0, 5)]),
    "disc_centre_hole": part("disc", _circles([(0, 0, 30)]), 8, [(0, 0, 6)]),
    "plate_four_holes": part(
        "plate4",
        _lines(_rect(100, 60)),
        10,
        [(-40, -20, 8), (40, -20, 8), (40, 20, 8), (-40, 20, 8)],
    ),
    "offset_hole": part("offset", _lines(_rect(50, 50)), 5, [(10, 0, 6)]),
    "cylinder": part("cylinder", _circles([(0, 0, 20)]), 40),
    "two_holes": part("two_holes", _lines(_rect(80, 40)), 6, [(-25, 0, 5), (25, 0, 5)]),
    "l_bracket_plate": part("l_plate", _lines(L_SHAPE), 8),
    "blind_hole_top_face": _top_face_hole(),
    "blind_hole_start_face": _start_face_hole(),
    "plate_slot": part("plate_slot", _slot(60, 20), 10),
    "plate_rectangles": _rectangles_plate(),
    "refuse_fillet": None,
    "refuse_hole_in_side_face": None,
    "refuse_assembly": None,
}
