"""Semantic and persistent geometry references (spec 7, ADR-049, ADR-070)."""

from cad_references.semantic import (
    SUPPORTED_ROLES,
    FaceRef,
    parse_face_plane,
    resolve_cap_face_signature,
)

__all__ = [
    "SUPPORTED_ROLES",
    "FaceRef",
    "parse_face_plane",
    "resolve_cap_face_signature",
]
