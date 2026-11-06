"""The evaluation prompts and the facts a correct answer must satisfy.

A case either expects a graph (``Facts``) or expects the agent to refuse (``facts is None``).
Expected volumes come from plain arithmetic, not from the code under test.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Facts:
    """What a correct graph must produce, independent of sketch plane and axis order."""

    size_mm: tuple[float, float, float]  # bounding box edges, sorted ascending
    volume_mm3: float
    cylinder_diameters_mm: tuple[float, ...]  # sorted ascending, base circle included


@dataclass(frozen=True, slots=True)
class Case:
    """One prompt; ``facts`` is None when the correct reply is a refusal."""

    case_id: str
    prompt: str
    facts: Facts | None


def _disc(diameter: float, depth: float) -> float:
    return math.pi * (diameter / 2) ** 2 * depth


CASES: tuple[Case, ...] = (
    Case(
        "block",
        "Make a block 40 x 30 x 10 mm.",
        Facts((10, 30, 40), 40 * 30 * 10, ()),
    ),
    Case(
        "block_centre_hole",
        "Create a part 40x30x10 mm with a 5 mm hole in the middle.",
        Facts((10, 30, 40), 40 * 30 * 10 - _disc(5, 10), (5,)),
    ),
    Case(
        "disc_centre_hole",
        "A round disc, 30 mm diameter, 8 mm thick, with a 6 mm hole in the centre.",
        Facts((8, 30, 30), _disc(30, 8) - _disc(6, 8), (6, 30)),
    ),
    Case(
        "plate_four_holes",
        "100 x 60 x 10 mm plate with four 8 mm holes, 10 mm in from each corner.",
        Facts((10, 60, 100), 100 * 60 * 10 - 4 * _disc(8, 10), (8, 8, 8, 8)),
    ),
    Case(
        "offset_hole",
        "50 x 50 x 5 plate with a 6 mm hole 10 mm right of the centre.",
        Facts((5, 50, 50), 50 * 50 * 5 - _disc(6, 5), (6,)),
    ),
    Case(
        "cylinder",
        "A solid cylinder, 20 mm diameter and 40 mm long.",
        Facts((20, 20, 40), _disc(20, 40), (20,)),
    ),
    Case(
        "two_holes",
        "80 x 40 x 6 plate with two 5 mm holes, 50 mm apart, centred.",
        Facts((6, 40, 80), 80 * 40 * 6 - 2 * _disc(5, 6), (5, 5)),
    ),
    Case(
        "l_bracket_plate",
        "An L-shaped plate 8 mm thick: 60 mm long, 40 mm tall, both arms 20 mm wide.",
        Facts((8, 40, 60), (60 * 20 + 20 * 20) * 8, ()),
    ),
    Case("refuse_fillet", "Make a 40 x 30 x 10 block and fillet all edges with 3 mm.", None),
    Case(
        "refuse_blind_hole_on_face",
        "Block 40 x 30 x 10 with a 5 mm hole 4 mm deep in the top face.",
        None,
    ),
    Case("refuse_assembly", "Make two plates and mate them together in an assembly.", None),
)
