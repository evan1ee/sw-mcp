"""D7: geometry inside the border and clear of the title block (spec 11.5)."""

from collections.abc import Sequence

from cad_drawing.checks.failures import CheckFailure, CheckItem, build_failure
from cad_drawing.checks.geometry2d import Vec, polygon_segments
from cad_drawing.checks.measure import Measurement, measure
from cad_drawing.checks.primitives import Prim
from cad_drawing.checks.snapshot import Rect, Sheet
from cad_drawing.checks.thresholds import CheckThresholds


def _rect_prim(owner: str, rect: Rect) -> Prim:
    lo, hi = rect.min, rect.max
    corners: tuple[Vec, Vec, Vec, Vec] = (lo, (hi[0], lo[1]), hi, (lo[0], hi[1]))
    segments = polygon_segments(corners, closed=True)
    return Prim("text_box", owner, segments, corners, None, None, 0)


def _points(p: Prim) -> list[Vec]:
    pts = [pt for s in p.segments for pt in (s.a, s.b)]
    if p.polygon is not None:
        pts.extend(p.polygon)
    return pts


def _outside(pt: Vec, border: Rect) -> float:
    return max(
        0.0,
        border.min[0] - pt[0],
        pt[0] - border.max[0],
        border.min[1] - pt[1],
        pt[1] - border.max[1],
    )


def _verdict(
    group: Sequence[Prim], sheet: Sheet, t: CheckThresholds
) -> tuple[Measurement, str | None] | None:
    """The border violation (farthest vertex) or else the first title-block contact."""
    worst: tuple[float, Vec, Prim] | None = None
    for p in group:
        for pt in _points(p):
            d = _outside(pt, sheet.border)
            if worst is None or d > worst[0]:
                worst = (d, pt, p)
    if worst is not None and worst[0] > t.epsilon_mm:
        return Measurement(worst[0], worst[1], worst[1]), worst[2].method
    for p in group:
        for i, rect in enumerate(sheet.title_block):
            m = measure(p, _rect_prim(f"title_block_{i}", rect))
            if m is not None and m.distance <= t.epsilon_mm:
                return Measurement(0.0, m.point_a, m.point_b), p.method
    return None


def check_d7(sheet: Sheet, prims: Sequence[Prim], t: CheckThresholds) -> tuple[CheckFailure, ...]:
    """One failure per view or annotation that leaves the border or touches the title block."""
    groups: dict[str, list[Prim]] = {}
    for p in prims:
        if not (p.kind == "edge" and p.in_view):
            groups.setdefault(p.owner, []).append(p)
    found: list[tuple[CheckItem, Measurement, str | None]] = []
    for view in sheet.views:
        verdict = _verdict([_rect_prim(view.key, view.outline)], sheet, t)
        if verdict is not None:
            found.append((CheckItem("view", view.key), *verdict))
    for key in sorted(groups):
        verdict = _verdict(groups[key], sheet, t)
        if verdict is not None:
            found.append((CheckItem("annotation", key), *verdict))
    return tuple(
        build_failure("D7", sheet.key, [(item, method)], m, t.epsilon_mm)
        for item, m, method in found
    )
