"""Exact 2D primitives for the drawing checks (spec 11.5.2).

Pure and float-based: nothing here rounds. Segments may be degenerate (zero length) and quads
may have zero area; every function stays total and returns the correct distance.
"""

import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from cad_ir.core import quantum

type Vec = tuple[float, float]

_TINY: Final = 1e-12
_FULL_TURN: Final = 360.0
_MITER_LIMIT: Final = 1e-9
_ANGLE_TOLERANCE: Final = float(quantum("angle"))


@dataclass(frozen=True, slots=True)
class Segment:
    a: Vec
    b: Vec


@dataclass(frozen=True, slots=True)
class Quad:
    """A convex quadrilateral; the vertex order may be clockwise or counter-clockwise."""

    corners: tuple[Vec, Vec, Vec, Vec]

    def edges(self) -> tuple[Segment, Segment, Segment, Segment]:
        c = self.corners
        return (
            Segment(c[0], c[1]),
            Segment(c[1], c[2]),
            Segment(c[2], c[3]),
            Segment(c[3], c[0]),
        )


def _cross(o: Vec, a: Vec, b: Vec) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def closest_point_on_segment(p: Vec, s: Segment) -> Vec:
    """The point of ``s`` nearest to ``p``; a zero-length segment is its single point."""
    dx, dy = s.b[0] - s.a[0], s.b[1] - s.a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return s.a
    t = ((p[0] - s.a[0]) * dx + (p[1] - s.a[1]) * dy) / length_sq
    t = min(1.0, max(0.0, t))
    return (s.a[0] + t * dx, s.a[1] + t * dy)


def point_segment_distance(p: Vec, s: Segment) -> float:
    c = closest_point_on_segment(p, s)
    return math.hypot(p[0] - c[0], p[1] - c[1])


def _properly_cross(s: Segment, t: Segment) -> bool:
    d1, d2 = _cross(t.a, t.b, s.a), _cross(t.a, t.b, s.b)
    d3, d4 = _cross(s.a, s.b, t.a), _cross(s.a, s.b, t.b)
    return (
        d1 != 0.0
        and d2 != 0.0
        and d3 != 0.0
        and d4 != 0.0
        and (d1 > 0.0) != (d2 > 0.0)
        and (d3 > 0.0) != (d4 > 0.0)
    )


def crossing_point(s: Segment, t: Segment) -> Vec | None:
    """The point where ``s`` and ``t`` properly cross; None for touching, parallel or apart."""
    if not _properly_cross(s, t):
        return None
    d1, d2 = _cross(t.a, t.b, s.a), _cross(t.a, t.b, s.b)
    k = d1 / (d1 - d2)
    return (s.a[0] + (s.b[0] - s.a[0]) * k, s.a[1] + (s.b[1] - s.a[1]) * k)


def segment_distance(s: Segment, t: Segment) -> float:
    """Minimum distance; 0 when they intersect, overlap collinearly or touch at an endpoint."""
    if _properly_cross(s, t):
        return 0.0
    return min(
        point_segment_distance(s.a, t),
        point_segment_distance(s.b, t),
        point_segment_distance(t.a, s),
        point_segment_distance(t.b, s),
    )


def closest_points(s: Segment, t: Segment) -> tuple[Vec, Vec]:
    """A pair of closest points, one on each segment (the crossing point twice if they cross)."""
    x = crossing_point(s, t)
    if x is not None:
        return (x, x)
    pairs = (
        (s.a, closest_point_on_segment(s.a, t)),
        (s.b, closest_point_on_segment(s.b, t)),
        (closest_point_on_segment(t.a, s), t.a),
        (closest_point_on_segment(t.b, s), t.b),
    )
    return min(pairs, key=lambda pr: math.dist(pr[0], pr[1]))


def segment_contacts(s: Segment, t: Segment, eps: float) -> tuple[tuple[Vec, Vec], ...]:
    """Every place where ``s`` and ``t`` come within ``eps``, as (point on s, point on t) pairs.

    A proper crossing is one contact. Otherwise each end point of either segment that lies within
    ``eps`` of the other is a contact, which for a collinear or near-parallel overlap gives the
    two ends of the overlap interval.
    """
    x = crossing_point(s, t)
    if x is not None:
        return ((x, x),)
    found: list[tuple[Vec, Vec]] = []
    for end in (s.a, s.b):
        near = closest_point_on_segment(end, t)
        if math.dist(end, near) <= eps:
            found.append((end, near))
    for end in (t.a, t.b):
        near = closest_point_on_segment(end, s)
        if math.dist(end, near) <= eps:
            found.append((near, end))
    return tuple(found)


def point_in_polygon(p: Vec, polygon: Sequence[Vec]) -> bool:
    """True when ``p`` lies inside or on the boundary of a simple polygon (winding number).

    Works for any orientation and for concave polygons; a self-intersecting polygon counts
    every region with a nonzero winding number as inside.
    """
    winding = 0
    count = len(polygon)
    for i in range(count):
        a, b = polygon[i], polygon[(i + 1) % count]
        side = _cross(a, b, p)
        if (
            side == 0.0
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
        ):
            return True
        if a[1] <= p[1]:
            if b[1] > p[1] and side > 0.0:
                winding += 1
        elif b[1] <= p[1] and side < 0.0:
            winding -= 1
    return winding != 0


def polygon_segments(points: Sequence[Vec], closed: bool) -> tuple[Segment, ...]:
    """Consecutive segments of a polyline or polygon; zero-length segments are dropped."""
    pairs = list(itertools.pairwise(points))
    if closed and points:
        pairs.append((points[-1], points[0]))
    return tuple(Segment(a, b) for a, b in pairs if a != b)


def arc_sweep_deg(start_deg: float, end_deg: float) -> float:
    """Counter-clockwise sweep in degrees, judged with the angle quantum as tolerance.

    ``(end - start) mod 360``, except that ends within the quantum of each other are a
    zero-length arc and ends that differ by a nonzero multiple of 360 (within the quantum) are
    a full circle (spec 11.5.1).
    """
    diff = end_deg - start_deg
    if abs(diff) <= _ANGLE_TOLERANCE:
        return 0.0
    wrapped = diff % _FULL_TURN
    if wrapped < _ANGLE_TOLERANCE or wrapped > _FULL_TURN - _ANGLE_TOLERANCE:
        return _FULL_TURN
    return wrapped


def tessellate_arc(
    center: Vec,
    radius: float,
    start_deg: float,
    end_deg: float,
    max_chord_error: float = 0.02,
) -> tuple[Vec, ...]:
    """Points along a counter-clockwise arc with a chord error of at most ``max_chord_error``.

    The sweep is ``arc_sweep_deg(start_deg, end_deg)``; a zero sweep gives one point.
    """
    sweep = arc_sweep_deg(start_deg, end_deg)
    start = math.radians(start_deg)

    def at(angle: float) -> Vec:
        return (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))

    if sweep == 0.0:
        return (at(start),)
    sweep_rad = math.radians(sweep)
    step = 2.0 * math.acos(1.0 - min(1.0, max_chord_error / radius))
    n = max(1, math.ceil(sweep_rad / step))
    return tuple(at(start + sweep_rad * i / n) for i in range(n + 1))


def _signed_area(q: Quad) -> float:
    c = q.corners
    return 0.5 * sum(c[i][0] * c[(i + 1) % 4][1] - c[(i + 1) % 4][0] * c[i][1] for i in range(4))


def _inflate_by_frame(q: Quad, d: float) -> Quad:
    """Degenerate fallback: the oriented bounding box along the longest edge, grown by ``d``."""
    longest = max(q.edges(), key=lambda e: math.dist(e.a, e.b))
    length = math.dist(longest.a, longest.b)
    if length < _TINY:
        ux, uy = 1.0, 0.0
    else:
        ux, uy = (longest.b[0] - longest.a[0]) / length, (longest.b[1] - longest.a[1]) / length
    vx, vy = -uy, ux
    us = [x * ux + y * uy for x, y in q.corners]
    vs = [x * vx + y * vy for x, y in q.corners]
    u0, u1, v0, v1 = min(us) - d, max(us) + d, min(vs) - d, max(vs) + d

    def back(u: float, v: float) -> Vec:
        return (u * ux + v * vx, u * uy + v * vy)

    return Quad((back(u0, v0), back(u1, v0), back(u1, v1), back(u0, v1)))


def inflate_quad(q: Quad, d: float) -> Quad:
    """Move every side outward by ``d`` along its normal (a rectangle grows by ``d`` per side)."""
    area = _signed_area(q)
    edges = q.edges()
    lengths = [math.dist(e.a, e.b) for e in edges]
    if abs(area) < _TINY or min(lengths) < _TINY:
        return _inflate_by_frame(q, d)
    sign = 1.0 if area > 0.0 else -1.0  # outward normal of (dx, dy) is (dy, -dx) when CCW
    normals = [
        (sign * (e.b[1] - e.a[1]) / n, -sign * (e.b[0] - e.a[0]) / n)
        for e, n in zip(edges, lengths, strict=True)
    ]
    out: list[Vec] = []
    for k in range(4):
        n1, n2 = normals[k - 1], normals[k]
        denom = 1.0 + n1[0] * n2[0] + n1[1] * n2[1]
        if denom < _MITER_LIMIT:
            return _inflate_by_frame(q, d)
        out.append(
            (
                q.corners[k][0] + d * (n1[0] + n2[0]) / denom,
                q.corners[k][1] + d * (n1[1] + n2[1]) / denom,
            )
        )
    return Quad((out[0], out[1], out[2], out[3]))


def aabb(points: Iterable[Vec]) -> tuple[float, float, float, float]:
    """``(min_x, min_y, max_x, max_y)`` of a non-empty point set."""
    xs, ys = zip(*points, strict=True)
    return (min(xs), min(ys), max(xs), max(ys))
