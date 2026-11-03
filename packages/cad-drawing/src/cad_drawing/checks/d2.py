"""D2: text overlapping text or other annotations' lines (spec 11.5.2)."""

from collections.abc import Sequence

from cad_drawing.checks.failures import (
    Candidate,
    CheckFailure,
    CheckItem,
    emit_failures,
    keep_min,
)
from cad_drawing.checks.measure import measure
from cad_drawing.checks.primitives import Prim
from cad_drawing.checks.snapshot import Sheet
from cad_drawing.checks.spatial import GridIndex
from cad_drawing.checks.thresholds import CheckThresholds

_LINE_KINDS = {"dimension_line", "extension_line", "arrowhead"}


def _is_text(p: Prim) -> bool:
    return p.kind == "text_box"


def _any(_: Prim) -> bool:
    return True


def check_d2(sheet: Sheet, prims: Sequence[Prim], t: CheckThresholds) -> tuple[CheckFailure, ...]:
    """Minimum distance per (owner, owner) pair and threshold class, strictly below clearance."""
    cand = [p for p in prims if p.kind == "text_box" or p.kind in _LINE_KINDS]
    pad = max(t.text_clearance_mm, t.line_clearance_mm)
    best: dict[tuple[str, ...], Candidate] = {}
    for a, b in GridIndex.build(cand).candidate_pairs(_is_text, _any, pad):
        if a.owner == b.owner:
            continue
        text_pair = b.kind == "text_box"
        threshold = t.text_clearance_mm if text_pair else t.line_clearance_mm
        m = measure(a, b)
        if m is None or m.distance >= threshold:
            continue
        owners = tuple(sorted((a.owner, b.owner)))
        entries = (
            (CheckItem("annotation", a.owner), a.method),
            (CheckItem("annotation", b.owner), b.method),
        )
        keep_min(best, (*owners, "text" if text_pair else "line"), (m, entries, threshold))
    return emit_failures("D2", sheet.key, best)
