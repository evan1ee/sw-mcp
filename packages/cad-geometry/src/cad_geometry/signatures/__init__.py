"""Cap-face frame and 2D-to-3D projection helpers across datum planes (ADR-070, K29)."""

from cad_ir.part_feature_graph.faces import FaceFrame, face_frame
from cad_ir.part_feature_graph.planes import plane_axes


def cap_face_frame(plane: str, depth: float, role: str) -> FaceFrame:
    """Resolve the 2D sketch frame on a cap face for a base extrude on ``plane``."""
    return face_frame(plane_axes(plane), depth, role)


def project_cap_face_point(
    plane: str,
    depth: float,
    role: str,
    point_2d: tuple[float, float],
    into_body_mm: float = 0.0,
) -> tuple[float, float, float]:
    """Project 2D cap-face point (x, y) and inward depth ``into_body_mm`` to 3D model space."""
    frame = cap_face_frame(plane, depth, role)
    base_d = depth - into_body_mm if role == "end_face" else into_body_mm
    return frame.to_model(point_2d[0], point_2d[1], base_d)


__all__ = ["FaceFrame", "cap_face_frame", "project_cap_face_point"]
