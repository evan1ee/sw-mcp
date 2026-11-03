"""Minimum distance and contact points between two check primitives."""

import math
from dataclasses import dataclass

from cad_drawing.checks.geometry2d import (
    Segment,
    Vec,
    closest_points,
    point_in_polygon,
    segment_contacts,
    segment_distance,
)
from cad_drawing.checks.primitives import Prim

type Contact = tuple[Vec, Vec]


@dataclass(frozen=True, slots=True)
class Measurement:
    distance: float
    point_a: Vec
    point_b: Vec


def _shape_segments(p: Prim) -> tuple[Segment, ...]:
    """Boundary segments; a polygon with no segments (a point box) acts as its first corner."""
    if p.segments or p.polygon is None:
        return p.segments
    c = p.polygon[0]
    return (Segment(c, c),)


def _gap(s: Segment, t: Segment) -> float:
    """Lower bound of the distance between two segments, from their bounding boxes."""
    dx = max(
        min(t.a[0], t.b[0]) - max(s.a[0], s.b[0]),
        min(s.a[0], s.b[0]) - max(t.a[0], t.b[0]),
        0.0,
    )
    dy = max(
        min(t.a[1], t.b[1]) - max(s.a[1], s.b[1]),
        min(s.a[1], s.b[1]) - max(t.a[1], t.b[1]),
        0.0,
    )
    return max(dx, dy)


def _containment(outer: Prim, inner: Prim) -> Vec | None:
    """A point of ``inner`` that lies inside the polygon of ``outer``, if any.

    The probe is the middle of the first segment, so a vertex that merely touches the outline
    cannot stand for the whole shape; without a boundary contact the inner shape is entirely in
    or entirely out, so one probe decides.
    """
    if outer.polygon is None:
        return None
    probe = _shape_segments(inner)
    if not probe:
        return None
    first = probe[0]
    point = ((first.a[0] + first.b[0]) / 2.0, (first.a[1] + first.b[1]) / 2.0)
    return point if point_in_polygon(point, outer.polygon) else None


def measure(p: Prim, q: Prim) -> Measurement | None:
    """Distance between two prims (0 on overlap or containment); None if either is empty."""
    sp, sq = _shape_segments(p), _shape_segments(q)
    if not sp or not sq:
        return None
    for outer, inner in ((p, q), (q, p)):
        inside = _containment(outer, inner)
        if inside is not None:
            return Measurement(0.0, inside, inside)
    best: tuple[Segment, Segment] = (sp[0], sq[0])
    best_d = float("inf")
    for s in sp:
        for t in sq:
            if _gap(s, t) >= best_d:
                continue
            d = segment_distance(s, t)
            if d < best_d:
                best, best_d = (s, t), d
    a, b = closest_points(*best)
    return Measurement(best_d, a, b)


def contacts(p: Prim, q: Prim, eps: float) -> tuple[Contact, ...]:
    """Every contact of two prims within ``eps``: (point on p, point on q) pairs, none if apart.

    Per segment pair: the proper crossing, or each end point within ``eps`` of the other
    segment (the ends of a collinear overlap). A shape inside the other polygon adds the probe
    point. Each pair is at most ``eps`` apart.
    """
    sp, sq = _shape_segments(p), _shape_segments(q)
    if not sp or not sq:
        return ()
    found: list[Contact] = []
    for s in sp:
        for t in sq:
            if _gap(s, t) <= eps:
                found.extend(segment_contacts(s, t, eps))
    for outer, inner in ((p, q), (q, p)):
        inside = _containment(outer, inner)
        if inside is not None:
            found.append((inside, inside))
    return tuple(found)


def contact_distance(contact: Contact) -> float:
    return math.dist(contact[0], contact[1])
