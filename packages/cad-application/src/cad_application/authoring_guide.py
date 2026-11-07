"""The IR authoring guide an agent reads before it writes a Part Feature Graph.

Built from the real plane definitions and the supported feature list, so it cannot drift from
the code. Worked examples are validated by the tests. The rules in ``_RULES`` mirror the
messages of ``cad_compiler.validator.semantic``; ``validate_part_graph`` stays the authority.
"""

import json
from dataclasses import dataclass
from typing import Any, Final

from cad_ir.part_feature_graph.planes import plane_axes

from cad_application.tools.list_feature_types import MVP_TYPES

_PLANES: Final[tuple[str, ...]] = ("plane:front", "plane:top", "plane:right")

_RULES: Final[tuple[str, ...]] = (
    'Units are millimetres: `units` is `"mm"` and `origin` is `"built"`.',
    "Node ids match `^[a-z][a-z0-9_]{0,63}$`. Every `profile` and `dependencies` entry names a"
    " node in the graph. A feature lists the sketch it uses and the nodes it builds on.",
    "A part has exactly one `extrude`. It is the base body; `cut_extrude` nodes remove material"
    " from it and must depend on it.",
    "An extrude profile is either one closed, non-self-intersecting loop of `line` entities or"
    " exactly one `circle`. Lines and circles are never mixed in one extrude profile.",
    "A cut profile is lines or circles, never both. Every cut shape lies strictly inside the"
    " extrude profile (not touching its edge) and cut shapes do not overlap each other.",
    "A sketch's `plane` is an origin plane or a cap face of the extrude: `<extrude_id>.end_face`"
    " (the face the extrude grows towards) or `<extrude_id>.start_face` (the face on the sketch"
    " plane). A sketch on a face lists the extrude in its `dependencies`.",
    "Lines have a non-zero length, circle diameters are at least 0.01 and depths are positive.",
    '`extrude` takes `{"type": "blind", "depth": D}`. `cut_extrude` takes the same, with D'
    ' smaller than the extrude depth, or `{"type": "through_all_both"}`.',
)

_UNSUPPORTED: Final[tuple[str, ...]] = (
    "fillets and chamfers",
    "arcs, splines, ellipses, text, and any outline that is not a closed loop of straight lines"
    " or a single circle",
    "patterns (linear, circular, mirror) as a feature; only write out shapes the user lists",
    "revolves, sweeps, lofts, shells, ribs, threads, sheet metal",
    "sketches on any face other than the extrude's start_face or end_face (side faces, faces"
    " of a cut), on an offset plane or on a datum",
    "more than one base extrude, or adding material after a cut",
    "assemblies, drawings, materials, custom properties and editing an existing part",
)


@dataclass(frozen=True, slots=True)
class Example:
    """A request sentence and the graph that fulfils it."""

    request: str
    graph: dict[str, Any]


def _rectangle(width: float, height: float) -> dict[str, Any]:
    x, y = width / 2, height / 2
    corners = [(-x, -y), (x, -y), (x, y), (-x, y)]
    return {
        f"l{i + 1}": {
            "type": "line",
            "start": list(corners[i]),
            "end": list(corners[(i + 1) % 4]),
        }
        for i in range(4)
    }


def _circle_sketch(diameter: float) -> dict[str, Any]:
    return {
        "type": "sketch",
        "plane": "plane:front",
        "entities": {"c1": {"type": "circle", "center": [0, 0], "diameter": diameter}},
    }


def _header(graph_id: str, nodes: dict[str, Any]) -> dict[str, Any]:
    return {
        "module": "part",
        "id": graph_id,
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": nodes,
    }


def _extrude(depth: float) -> dict[str, Any]:
    return {
        "type": "extrude",
        "dependencies": ["sketch_base"],
        "profile": "sketch_base",
        "end_condition": {"type": "blind", "depth": depth},
    }


def _build_examples() -> dict[str, Example]:
    rectangle = {"type": "sketch", "plane": "plane:front", "entities": _rectangle(40, 30)}
    hole_cut = {
        "type": "cut_extrude",
        "dependencies": ["sketch_hole", "extrude_base"],
        "profile": "sketch_hole",
        "end_condition": {"type": "through_all_both"},
    }
    top_hole_sketch = _circle_sketch(5)
    top_hole_sketch["plane"] = "extrude_base.end_face"
    top_hole_sketch["dependencies"] = ["extrude_base"]
    top_hole_cut = {
        "type": "cut_extrude",
        "dependencies": ["sketch_hole", "extrude_base"],
        "profile": "sketch_hole",
        "end_condition": {"type": "blind", "depth": 4},
    }
    return {
        "block_top_hole": Example(
            "Make a 40 x 30 x 10 mm block with a 5 mm hole, 4 mm deep, in the top face.",
            _header(
                "block_40x30x10_top_hole",
                {
                    "sketch_base": rectangle,
                    "extrude_base": _extrude(10),
                    "sketch_hole": top_hole_sketch,
                    "cut_hole": top_hole_cut,
                },
            ),
        ),
        "block": Example(
            "Make a 40 x 30 x 10 mm block.",
            _header("block_40x30x10", {"sketch_base": rectangle, "extrude_base": _extrude(10)}),
        ),
        "block_with_hole": Example(
            "Make a 40 x 30 x 10 mm block with a 5 mm hole through the middle.",
            _header(
                "block_40x30x10_hole5",
                {
                    "sketch_base": rectangle,
                    "extrude_base": _extrude(10),
                    "sketch_hole": _circle_sketch(5),
                    "cut_hole": hole_cut,
                },
            ),
        ),
        "disc_with_hole": Example(
            "Make a round disc, 30 mm diameter and 8 mm thick, with a 6 mm hole in the centre.",
            _header(
                "disc_d30x8_hole6",
                {
                    "sketch_base": _circle_sketch(30),
                    "extrude_base": _extrude(8),
                    "sketch_hole": _circle_sketch(6),
                    "cut_hole": hole_cut,
                },
            ),
        ),
    }


EXAMPLES: Final[dict[str, Example]] = _build_examples()


def _plane_rows() -> list[str]:
    rows = [
        "| plane | sketch x axis | sketch y axis | normal (extrude direction) |",
        "|---|---|---|---|",
    ]
    for name in _PLANES:
        axes = plane_axes(name)
        rows.append(f"| `{name}` | {axes.x_axis} | {axes.y_axis} | {axes.normal} |")
    return rows


def build_guide() -> str:
    """Return the authoring guide as Markdown."""
    lines: list[str] = [
        "# Writing a Part Feature Graph for sw-mcp",
        "",
        "## Workflow",
        "1. Decide whether the request is within the limits below. If it is not, stop:"
        " reply that you cannot fulfil it and name what the MVP cannot do."
        " Do not approximate it with something similar, and do not build part of it.",
        "2. Write the graph following the rules below.",
        "3. Call `validate_part_graph`. Fix every issue it reports and call it again until"
        " `valid` is true.",
        "4. Compare the `expected` geometry (bounding box, volume, hole count and size) with the"
        " request. Tell the user what you are about to build.",
        "5. Call `apply_part_graph` with `graph` and `target_path`, then poll"
        " `get_execution_status` until the job reaches `COMMITTED` or `FAILED`."
        " Report the outcome, including any `PART_VERIFICATION_FAILED` details, honestly.",
        "",
        "## Node types",
    ]
    lines += [f"- `{name}`: {description}" for name, description in MVP_TYPES]
    lines += [
        "",
        "Call `get_feature_schema` for the exact fields of a type.",
        "",
        "## Planes and directions",
        "Sketch coordinates are 2D, in mm, on the sketch plane. An extrude grows along the plane"
        " normal from the sketch plane. The origin is the middle of the sketch, so a centred"
        " shape uses coordinates symmetric about (0, 0).",
        "",
        *_plane_rows(),
        "",
        "A blind cut from an origin plane starts at that plane and goes into the body along the"
        " normal. A blind cut from a cap face goes into the body, against the face's outward"
        " normal, so a hole from `end_face` is that deep below the top. Use `through_all_both`"
        " for a hole through the part.",
        "",
        "## Sketching on a cap face",
        "Every extrude has two cap faces along its base plane's normal (`plane:front`,"
        " `plane:top`, or `plane:right`): `end_face` (at offset = the extrude depth along the"
        " base normal) and `start_face` (at offset = 0 on the base sketch plane). Coordinates"
        " are in mm from the model origin. On `end_face` the sketch axes equal the base plane's"
        " axes. On `start_face` the sketch x axis is mirrored (you look at the face from"
        " outside), so x = 10 maps to -10 along the base plane's x axis. The build checks the"
        " real frame and fails with `REF_SIGNATURE_MISMATCH` when it differs.",
        "",
        "## Rules the validator enforces",
    ]
    lines += [f"- {rule}" for rule in _RULES]
    lines += [
        "",
        "## Not supported - refuse these",
        "If the request needs any of the following, reply that you cannot fulfil it.",
    ]
    lines += [f"- {item}" for item in _UNSUPPORTED]
    lines += ["", "## Worked examples"]
    for name in sorted(EXAMPLES):
        example = EXAMPLES[name]
        lines += [
            "",
            f'### {name}: "{example.request}"',
            "```json",
            json.dumps(example.graph, indent=2),
            "```",
        ]
    return "\n".join(lines) + "\n"
