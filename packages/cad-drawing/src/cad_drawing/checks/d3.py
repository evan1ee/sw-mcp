"""D3: text over model edges (spec 11.5.2)."""

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


def check_d3(sheet: Sheet, prims: Sequence[Prim], t: CheckThresholds) -> tuple[CheckFailure, ...]:
    """A text box strictly closer than ``edge_clearance_mm`` to a model edge."""
    cand = [p for p in prims if p.kind in {"text_box", "edge"}]
    best: dict[tuple[str, ...], Candidate] = {}
    for text, edge in GridIndex.build(cand).candidate_pairs(
        lambda p: p.kind == "text_box", lambda p: p.kind == "edge", t.edge_clearance_mm
    ):
        if not edge.in_view and edge.owner == text.owner:
            continue  # an annotation's own center line never fails against its own text
        m = measure(text, edge)
        if m is None or m.distance >= t.edge_clearance_mm:
            continue
        item = (
            CheckItem("edge", edge.owner, edge.index)
            if edge.in_view
            else CheckItem("annotation", edge.owner)
        )
        entries = ((CheckItem("annotation", text.owner), text.method), (item, None))
        key = (text.owner, edge.owner, f"{edge.index if edge.in_view else 0:09d}")
        keep_min(best, key, (m, entries, t.edge_clearance_mm))
    return emit_failures("D3", sheet.key, best)
