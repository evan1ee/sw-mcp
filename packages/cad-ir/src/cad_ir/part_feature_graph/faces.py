"""Sketches on an extrude's cap faces (ADR-070, spec 5.7.4).

A sketch ``plane`` of the form ``<extrude_id>.<role>`` names a face of that extrude. Only the two
cap faces are supported across all three standard base planes (``plane:front``, ``plane:top``,
``plane:right``). The add-in checks the opened sketch's real frame against the stated axes.
"""

import re
from dataclasses import dataclass, replace
from typing import Final

from cad_ir.part_feature_graph.model import Circle, Line, PartGraph, SketchNode
from cad_ir.part_feature_graph.planes import PlaneAxes

SUPPORTED_ROLES: Final[tuple[str, ...]] = ("start_face", "end_face")

_NON_FACE_PREFIXES: Final[tuple[str, ...]] = ("plane:", "geo:", "datum:")
_FACE_PLANE: Final = re.compile(r"^([a-z][a-z0-9_]{0,63})\.([a-z][a-z0-9_]{0,63})$")


@dataclass(frozen=True, slots=True)
class FaceRef:
    """A node id and a role, such as ``extrude_base`` and ``end_face``."""

    node_id: str
    role: str


@dataclass(frozen=True, slots=True)
class FaceFrame:
    """The sketch frame on a cap face, in model space, and how a cut from it is placed."""

    role: str
    x_axis: tuple[float, float, float]
    y_axis: tuple[float, float, float]
    normal: tuple[float, float, float]  # outward unit normal of the face
    offset_mm: float  # signed distance of the face plane from the model origin along ``normal``
    x_sign: float  # 1.0 when sketch x equals the base plane's x, -1.0 when mirrored
    base_normal: tuple[float, float, float]

    def into_body_depth_from_base(self, depth: float, cut: float) -> tuple[float, float]:
        """The span, along the base plane's normal, that a blind cut of ``cut`` mm covers.

        A cut from a face goes into the body, against the face's outward normal. Returns
        ``(low, high)`` measured from the base plane.
        """
        if self.role == "end_face":
            return (depth - cut, depth)
        return (0.0, cut)

    def to_model(
        self,
        x: float,
        y: float,
        depth_from_base: float | None = None,
    ) -> tuple[float, float, float]:
        """Map 2D face sketch coordinates (x, y) to 3D model coordinates (X, Y, Z)."""
        d = self.offset_mm if depth_from_base is None else depth_from_base
        return (
            x * self.x_axis[0] + y * self.y_axis[0] + d * self.base_normal[0],
            x * self.x_axis[1] + y * self.y_axis[1] + d * self.base_normal[1],
            x * self.x_axis[2] + y * self.y_axis[2] + d * self.base_normal[2],
        )


def parse_face_plane(plane: str) -> FaceRef | None:
    """Return the face reference in ``plane``, or None for a standard plane or other host."""
    if plane == "origin" or plane.startswith(_NON_FACE_PREFIXES):
        return None
    match = _FACE_PLANE.match(plane)
    if match is None:
        return None
    return FaceRef(match.group(1), match.group(2))


def face_frame(base: PlaneAxes, depth: float, role: str) -> FaceFrame:
    """Return the frame of a cap face of an extrude of ``depth`` mm whose sketch is on ``base``."""
    if role == "end_face":
        return FaceFrame(
            role=role,
            x_axis=base.x_axis,
            y_axis=base.y_axis,
            normal=base.normal,
            offset_mm=depth,
            x_sign=1.0,
            base_normal=base.normal,
        )
    if role == "start_face":
        bx, by, bz = base.normal
        return FaceFrame(
            role=role,
            x_axis=(-base.x_axis[0], -base.x_axis[1], -base.x_axis[2]),
            y_axis=base.y_axis,
            normal=(-bx, -by, -bz),
            offset_mm=0.0,
            x_sign=-1.0,
            base_normal=base.normal,
        )
    raise ValueError(f"unsupported face role {role!r}: use start_face or end_face")


def _mirror_x(entity: Line | Circle) -> Line | Circle:
    if isinstance(entity, Line):
        return Line(start=(-entity.start[0], entity.start[1]), end=(-entity.end[0], entity.end[1]))
    return Circle(center=(-entity.center[0], entity.center[1]), diameter=entity.diameter)


def in_base_frame(graph: PartGraph) -> PartGraph:
    """Return the graph with every start-face sketch mirrored into the base sketch frame.

    A start face has x mirrored against the base plane (ADR-070), so checks that compare a cut
    with the base profile must see both in one frame. Other sketches are returned unchanged.
    """
    nodes = dict(graph.nodes)
    for node_id, node in graph.nodes.items():
        if not isinstance(node, SketchNode):
            continue
        face = parse_face_plane(node.plane)
        if face is not None and face.role == "start_face":
            mirrored = {key: _mirror_x(ent) for key, ent in node.entities.items()}
            nodes[node_id] = replace(node, entities=mirrored)
    return replace(graph, nodes=nodes)
