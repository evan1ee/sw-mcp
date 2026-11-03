"""Geometric soft metrics (spec 11.5): counted, never failing."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from cad_ir.core import JsonValue

from cad_drawing.checks.arrangement import coincident
from cad_drawing.checks.geometry2d import Vec
from cad_drawing.checks.measure import Contact, contacts, measure
from cad_drawing.checks.primitives import Prim
from cad_drawing.checks.snapshot import Sheet
from cad_drawing.checks.spatial import GridIndex
from cad_drawing.checks.thresholds import CheckThresholds

_COUNTED_EDGES: Final = frozenset({"visible", "silhouette"})


@dataclass(frozen=True, slots=True)
class SoftMetrics:
    extension_crossings: int
    dimension_lines_over_edges: int
    view_count: int
    sheet_size_mm: Vec

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "extension_crossings": self.extension_crossings,
            "dimension_lines_over_edges": self.dimension_lines_over_edges,
            "view_count": self.view_count,
            "sheet_size_mm": [self.sheet_size_mm[0], self.sheet_size_mm[1]],
        }


def _terminal_only(leader: Prim, found: Sequence[Contact], eps: float) -> bool:
    """Every contact lies at an end point of the leader: it touches the edge it points at."""
    ends = (leader.segments[0].a, leader.segments[-1].b) if leader.segments else ()
    return all(any(math.dist(c[0], end) <= eps for end in ends) for c in found)


def _model_edge(p: Prim) -> bool:
    return p.kind == "edge" and p.in_view and p.edge_kind in _COUNTED_EDGES


def compute_soft_metrics(sheet: Sheet, prims: Sequence[Prim], t: CheckThresholds) -> SoftMetrics:
    """Extension-line crossings and dimension lines over visible model edges, within epsilon.

    Extension lines shared by a chain or baseline arrangement are not crossings; a leader
    touching the edge it points at is not a line over an edge.
    """
    eps = t.epsilon_mm
    ext = [p for p in prims if p.kind == "extension_line"]
    dims = [p for p in prims if p.kind == "dimension_line"]
    edges = [p for p in prims if _model_edge(p)]
    index = GridIndex.build([*ext, *dims, *edges])
    crossings = 0
    for a, b in index.candidate_pairs(lambda p: p.kind == "extension_line", None, eps):
        m = measure(a, b)
        if a.owner != b.owner and m is not None and m.distance <= eps and not coincident(a, b, eps):
            crossings += 1
    over: set[tuple[str, str, int]] = set()
    for line, edge in index.candidate_pairs(lambda p: p.kind == "dimension_line", _model_edge, eps):
        found = contacts(line, edge, eps)
        if found and not (line.leader and _terminal_only(line, found, eps)):
            over.add((line.owner, edge.owner, edge.index))
    return SoftMetrics(crossings, len(over), len(sheet.views), sheet.size_mm)
