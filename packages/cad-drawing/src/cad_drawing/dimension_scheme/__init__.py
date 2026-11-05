"""Dimension scheme resolution and duplicate cleanup engine (spec 11.4, 11.10.1)."""

from cad_drawing.dimension_scheme.cleanup import (
    DuplicatePlan,
    HideAction,
    apply_cleanup_to_scheme,
    plan_duplicate_cleanup,
)
from cad_drawing.dimension_scheme.resolver import resolve_scheme_from_snapshot

__all__ = [
    "DuplicatePlan",
    "HideAction",
    "apply_cleanup_to_scheme",
    "plan_duplicate_cleanup",
    "resolve_scheme_from_snapshot",
]
