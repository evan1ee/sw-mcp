"""Semantic cap-face reference parsing and signature resolution across datum planes (ADR-070)."""

from typing import Any

from cad_geometry.signatures import cap_face_frame
from cad_ir.part_feature_graph import PartGraph, SketchNode, SolidNode
from cad_ir.part_feature_graph.faces import SUPPORTED_ROLES, FaceRef, parse_face_plane


def resolve_cap_face_signature(graph: PartGraph, plane: str) -> dict[str, Any] | None:
    """Resolve cap-face signature and frame for ``plane`` in ``graph``, or None for non-faces."""
    face = parse_face_plane(plane)
    if face is None:
        return None
    parent = graph.nodes.get(face.node_id)
    if not isinstance(parent, SolidNode) or parent.type != "extrude":
        raise ValueError(f"Face reference parent {face.node_id!r} is not an extrude SolidNode")
    base_sketch = graph.nodes.get(parent.profile)
    if not isinstance(base_sketch, SketchNode):
        raise ValueError(f"Parent profile {parent.profile!r} is not a SketchNode")
    depth = float(parent.end_condition.depth or 0.0)
    frame = cap_face_frame(base_sketch.plane, depth, face.role)
    return {
        "feature": face.node_id,
        "role": face.role,
        "normal": list(frame.normal),
        "offset_mm": frame.offset_mm,
        "x_axis": list(frame.x_axis),
        "y_axis": list(frame.y_axis),
    }


__all__ = ["SUPPORTED_ROLES", "FaceRef", "parse_face_plane", "resolve_cap_face_signature"]
