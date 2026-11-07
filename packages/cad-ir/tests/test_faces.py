"""Face references of the part feature graph (ADR-070, spec 5.7.4)."""

from typing import Final

import pytest
from cad_ir.part_feature_graph.faces import FaceRef, face_frame, in_base_frame, parse_face_plane
from cad_ir.part_feature_graph.model import (
    CenterRectangle,
    CornerRectangle,
    EndCondition,
    PartGraph,
    SketchNode,
    SolidNode,
    StraightSlot,
)
from cad_ir.part_feature_graph.planes import plane_axes

DEPTH = 10.0
CUT = 4.0
TOP_DEPTH = 8.0
RECT_DIM: Final[float] = 10.0
SLOT_WIDTH: Final[float] = 6.0


def test_parses_a_face_reference() -> None:
    assert parse_face_plane("extrude_base.end_face") == FaceRef("extrude_base", "end_face")
    assert parse_face_plane("e.start_face") == FaceRef("e", "start_face")


@pytest.mark.parametrize("plane", ["plane:front", "geo:abc", "datum:A", "origin", "frontplane"])
def test_other_planes_are_not_face_references(plane: str) -> None:
    assert parse_face_plane(plane) is None


def test_an_unsupported_role_still_parses_so_the_validator_can_name_it() -> None:
    assert parse_face_plane("extrude_base.side_faces") == FaceRef("extrude_base", "side_faces")


def test_end_face_keeps_the_base_axes_and_moves_by_the_depth() -> None:
    frame = face_frame(plane_axes("plane:front"), DEPTH, "end_face")
    assert frame.x_axis == (1.0, 0.0, 0.0)
    assert frame.y_axis == (0.0, 1.0, 0.0)
    assert frame.normal == (0.0, 0.0, 1.0)
    assert frame.offset_mm == DEPTH
    assert frame.x_sign == 1.0
    assert frame.into_body_depth_from_base(depth=DEPTH, cut=CUT) == (DEPTH - CUT, DEPTH)


def test_start_face_mirrors_x_and_reverses_the_normal() -> None:
    frame = face_frame(plane_axes("plane:front"), DEPTH, "start_face")
    assert frame.x_axis == (-1.0, 0.0, 0.0)
    assert frame.y_axis == (0.0, 1.0, 0.0)
    assert frame.normal == (0.0, 0.0, -1.0)
    assert frame.offset_mm == 0.0
    assert frame.x_sign == -1.0
    assert frame.into_body_depth_from_base(depth=DEPTH, cut=CUT) == (0.0, CUT)


@pytest.mark.parametrize(
    ("plane", "role", "exp_axes", "exp_offset", "exp_model_pt"),
    [
        (
            "plane:front",
            "end_face",
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            DEPTH,
            (10.0, 5.0, 10.0),
        ),
        (
            "plane:front",
            "start_face",
            ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)),
            0.0,
            (-10.0, 5.0, 0.0),
        ),
        (
            "plane:top",
            "end_face",
            ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
            DEPTH,
            (10.0, 10.0, -5.0),
        ),
        (
            "plane:top",
            "start_face",
            ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
            0.0,
            (10.0, 0.0, 5.0),
        ),
        (
            "plane:right",
            "end_face",
            ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
            DEPTH,
            (10.0, 5.0, -10.0),
        ),
        (
            "plane:right",
            "start_face",
            ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
            0.0,
            (0.0, 5.0, 10.0),
        ),
    ],
)
def test_all_six_datum_and_cap_combinations_resolve_frame_and_3d_projection(
    plane: str,
    role: str,
    exp_axes: tuple[
        tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]
    ],
    exp_offset: float,
    exp_model_pt: tuple[float, float, float],
) -> None:
    frame = face_frame(plane_axes(plane), DEPTH, role)
    assert (frame.x_axis, frame.y_axis, frame.normal) == exp_axes
    assert frame.offset_mm == exp_offset
    assert frame.to_model(10.0, 5.0) == exp_model_pt


def test_the_frame_follows_the_base_plane() -> None:
    frame = face_frame(plane_axes("plane:top"), TOP_DEPTH, "end_face")
    assert frame.normal == (0.0, 1.0, 0.0)
    assert frame.offset_mm == TOP_DEPTH


def test_an_unsupported_role_has_no_frame() -> None:
    with pytest.raises(ValueError, match="side_faces"):
        face_frame(plane_axes("plane:front"), DEPTH, "side_faces")


def test_start_face_mirrors_rectangles() -> None:
    graph = PartGraph(
        id="mirrored_rect",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={"r1": CornerRectangle(corner1=(-50, -30), corner2=(50, 30))},
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=DEPTH),
                dependencies=("sketch_base",),
            ),
            "sketch_cut": SketchNode(
                plane="extrude_base.start_face",
                entities={
                    "cr1": CornerRectangle(corner1=(10, 10), corner2=(20, 20)),
                    "ctr1": CenterRectangle(center=(15, 15), width=RECT_DIM, height=RECT_DIM),
                },
                dependencies=("extrude_base",),
            ),
        },
    )
    mirrored = in_base_frame(graph)
    cut = mirrored.nodes["sketch_cut"]
    assert isinstance(cut, SketchNode)
    cr1 = cut.entities["cr1"]
    assert isinstance(cr1, CornerRectangle)
    # plane:front start_face has x_sign = -1.0, y_sign = 1.0
    assert cr1.corner1 == (-10.0, 10.0)
    assert cr1.corner2 == (-20.0, 20.0)

    ctr1 = cut.entities["ctr1"]
    assert isinstance(ctr1, CenterRectangle)
    assert ctr1.center == (-15.0, 15.0)
    assert ctr1.width == RECT_DIM
    assert ctr1.height == RECT_DIM


def test_start_face_mirrors_straight_slots() -> None:
    graph = PartGraph(
        id="mirrored_slot",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={"s1": StraightSlot(start_point=(-20, 0), end_point=(20, 0), width=10)},
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=DEPTH),
                dependencies=("sketch_base",),
            ),
            "sketch_cut": SketchNode(
                plane="extrude_base.start_face",
                entities={
                    "slot_cut": StraightSlot(start_point=(5, 10), end_point=(15, 10), width=6),
                },
                dependencies=("extrude_base",),
            ),
        },
    )
    mirrored = in_base_frame(graph)
    cut = mirrored.nodes["sketch_cut"]
    assert isinstance(cut, SketchNode)
    slot_cut = cut.entities["slot_cut"]
    assert isinstance(slot_cut, StraightSlot)
    # plane:front start_face has x_sign = -1.0, y_sign = 1.0
    assert slot_cut.start_point == (-5.0, 10.0)
    assert slot_cut.end_point == (-15.0, 10.0)
    assert slot_cut.width == SLOT_WIDTH
