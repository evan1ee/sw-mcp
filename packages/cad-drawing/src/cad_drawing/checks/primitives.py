"""Check primitives built from a sheet (spec 11.5.2 primitives table)."""

from dataclasses import dataclass
from typing import Final, Literal

from cad_drawing.checks.geometry2d import (
    Quad,
    Segment,
    Vec,
    inflate_quad,
    polygon_segments,
    tessellate_arc,
)
from cad_drawing.checks.snapshot import (
    Annotation,
    ArcCurve,
    Curve,
    EdgeKind,
    PolylineCurve,
    Sheet,
    TextBox,
)
from cad_drawing.checks.thresholds import CheckThresholds

type PrimKind = Literal["dimension_line", "extension_line", "arrowhead", "text_box", "edge"]

_KIND_RANK: Final[dict[PrimKind, int]] = {
    "dimension_line": 0,
    "extension_line": 1,
    "arrowhead": 2,
    "text_box": 3,
    "edge": 4,
}
_LINE_ONLY_KINDS: Final = frozenset({"center_mark", "centerline"})


@dataclass(frozen=True, slots=True)
class Prim:
    """One shape under test.

    ``owner`` is the annotation key (annotation prims) or the view key (view edges). ``index``
    is the position in the source list; leaders follow the dimension lines in one numbering.
    ``entity`` is set only for extension lines. ``polygon`` is the closed outline of text boxes
    and arrowheads (any point count, either orientation, possibly concave). Edge prims carry
    their ``edge_kind``; ``in_view`` tells a model edge from the center-mark and centerline line
    work of an annotation. ``leader`` marks leader polylines.
    """

    kind: PrimKind
    owner: str
    segments: tuple[Segment, ...]
    polygon: tuple[Vec, ...] | None
    method: str | None
    entity: str | None
    index: int
    edge_kind: EdgeKind | None = None
    in_view: bool = False
    leader: bool = False


def _curve_segments(curve: Curve, t: CheckThresholds) -> tuple[Segment, ...]:
    match curve:
        case PolylineCurve(points=points):
            return polygon_segments(points, closed=False)
        case ArcCurve(center=center, radius=radius, start_deg=start, end_deg=end):
            arc_points = tessellate_arc(center, radius, start, end, t.arc_chord_error_mm)
            return polygon_segments(arc_points, closed=False)


def _text_box_prim(owner: str, index: int, box: TextBox, t: CheckThresholds) -> Prim:
    quad = Quad(box.corners)
    if box.method == "font_metrics":
        quad = inflate_quad(quad, t.font_metric_margin * box.height_mm)
    return Prim(
        "text_box",
        owner,
        polygon_segments(quad.corners, closed=True),
        quad.corners,
        box.method,
        None,
        index,
    )


def _arrowhead_prim(owner: str, index: int, polygon: tuple[Vec, ...]) -> Prim:
    segments = polygon_segments(polygon, closed=True)
    return Prim("arrowhead", owner, segments, polygon, None, None, index)


def _line_work(a: Annotation, t: CheckThresholds) -> list[Prim]:
    """Dimension lines and leaders; center marks and centerlines become edge-class prims."""
    edge_kind: EdgeKind | None = None
    if a.kind == "center_mark":
        edge_kind = "center_mark"
    elif a.kind == "centerline":
        edge_kind = "centerline"
    kind: PrimKind = "dimension_line" if edge_kind is None else "edge"
    prims = [
        Prim(kind, a.key, _curve_segments(c, t), None, None, None, i, edge_kind)
        for i, c in enumerate(a.dimension_lines)
    ]
    offset = len(a.dimension_lines)
    prims.extend(
        Prim(
            kind,
            a.key,
            polygon_segments(leader, closed=False),
            None,
            None,
            None,
            offset + i,
            edge_kind,
            leader=edge_kind is None,
        )
        for i, leader in enumerate(a.leaders)
    )
    return prims


def sheet_primitives(sheet: Sheet, t: CheckThresholds) -> tuple[Prim, ...]:
    """All prims of a sheet, ordered by (owner, kind, index)."""
    prims: list[Prim] = []
    for a in sheet.annotations:
        prims.extend(_line_work(a, t))
        for i, ext in enumerate(a.extension_lines):
            segments = polygon_segments(ext.line, closed=False)
            prims.append(Prim("extension_line", a.key, segments, None, None, ext.entity, i))
        prims.extend(_arrowhead_prim(a.key, i, ah.polygon) for i, ah in enumerate(a.arrowheads))
        prims.extend(_text_box_prim(a.key, i, box, t) for i, box in enumerate(a.text_boxes))
    for view in sheet.views:
        for i, edge in enumerate(view.edges):
            segments = _curve_segments(edge.curve, t)
            prims.append(Prim("edge", view.key, segments, None, None, None, i, edge.kind, True))
    prims.sort(key=lambda p: (p.owner, _KIND_RANK[p.kind], p.index))
    return tuple(prims)
