"""2D primitives for the drawing checks (spec 11.5.2): distances are exact, touching is 0."""

import itertools
import math

import pytest
from cad_drawing.checks.geometry2d import (
    Quad,
    Segment,
    Vec,
    aabb,
    arc_sweep_deg,
    closest_points,
    crossing_point,
    inflate_quad,
    point_in_polygon,
    point_segment_distance,
    polygon_segments,
    segment_contacts,
    segment_distance,
    tessellate_arc,
)
from cad_drawing.checks.measure import measure
from cad_drawing.checks.primitives import Prim

ABS = 1e-12
FULL_TURN = 360.0


def _quad_prim(q: Quad) -> Prim:
    return Prim("text_box", "q", polygon_segments(q.corners, closed=True), q.corners, None, None, 0)


def quad_distance(q: Quad, r: Quad) -> float:
    m = measure(_quad_prim(q), _quad_prim(r))
    assert m is not None
    return m.distance


def segment_quad_distance(s: Segment, q: Quad) -> float:
    m = measure(Prim("dimension_line", "s", (s,), None, None, None, 0), _quad_prim(q))
    assert m is not None
    return m.distance


def square(cx: float, cy: float, half: float, *, clockwise: bool = False) -> Quad:
    corners: tuple[Vec, Vec, Vec, Vec] = (
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    )
    if clockwise:
        corners = (corners[0], corners[3], corners[2], corners[1])
    return Quad(corners)


def rotated_square(half: float, degrees: float) -> Quad:
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    base = ((-half, -half), (half, -half), (half, half), (-half, half))
    a, b, d, e = ((x * c - y * s, x * s + y * c) for x, y in base)
    return Quad((a, b, d, e))


def test_point_segment_distance() -> None:
    s = Segment((0, 0), (10, 0))
    assert point_segment_distance((5, 3), s) == pytest.approx(3.0, abs=ABS)
    assert point_segment_distance((-3, 4), s) == pytest.approx(5.0, abs=ABS)
    assert point_segment_distance((13, 4), s) == pytest.approx(5.0, abs=ABS)


def test_crossing_segments_zero() -> None:
    assert segment_distance(Segment((0, 0), (2, 2)), Segment((0, 2), (2, 0))) == 0.0


def test_parallel_distance() -> None:
    a, b = Segment((0, 0), (10, 0)), Segment((0, 1), (10, 1))
    assert segment_distance(a, b) == pytest.approx(1.0, abs=ABS)


def test_endpoint_touch_zero() -> None:
    assert segment_distance(Segment((0, 0), (1, 1)), Segment((1, 1), (2, 0))) == 0.0
    assert segment_distance(Segment((0, 0), (2, 0)), Segment((1, 0), (1, 5))) == 0.0


def test_collinear_overlap_zero() -> None:
    assert segment_distance(Segment((0, 0), (5, 0)), Segment((3, 0), (9, 0))) == 0.0
    assert segment_distance(Segment((0, 0), (5, 0)), Segment((1, 0), (2, 0))) == 0.0


def test_collinear_gap() -> None:
    a, b = Segment((0, 0), (1, 0)), Segment((3, 0), (4, 0))
    assert segment_distance(a, b) == pytest.approx(2.0, abs=ABS)


def test_degenerate_segments() -> None:
    point = Segment((3, 4), (3, 4))
    assert point_segment_distance((0, 0), point) == pytest.approx(5.0, abs=ABS)
    assert segment_distance(point, Segment((0, 0), (0, 0))) == pytest.approx(5.0, abs=ABS)
    assert segment_distance(point, Segment((0, 4), (10, 4))) == 0.0
    assert segment_distance(point, Segment((0, 0), (10, 0))) == pytest.approx(4.0, abs=ABS)
    assert segment_distance(Segment((0, 0), (10, 0)), point) == pytest.approx(4.0, abs=ABS)


def test_segment_quad_distance() -> None:
    q = square(0, 0, 1)
    assert segment_quad_distance(Segment((3, -5), (3, 5)), q) == pytest.approx(2.0, abs=ABS)
    assert segment_quad_distance(Segment((-5, 0), (5, 0)), q) == 0.0  # passes through
    assert segment_quad_distance(Segment((-0.5, 0), (0.5, 0.2)), q) == 0.0  # fully inside
    assert segment_quad_distance(Segment((1, 5), (1, -5)), q) == 0.0  # along a side


def test_quad_overlap_and_containment_zero() -> None:
    assert quad_distance(square(0, 0, 2), square(1, 1, 2)) == 0.0
    assert quad_distance(square(0, 0, 5), square(0, 0, 1)) == 0.0
    assert quad_distance(square(0, 0, 1), square(0, 0, 5)) == 0.0


def test_quad_contains_quad_zero() -> None:
    outer = square(0, 0, 10, clockwise=True)
    assert quad_distance(outer, square(2, 2, 1)) == 0.0
    assert quad_distance(square(2, 2, 1), outer) == 0.0


def test_quad_gap_and_orientation_independent() -> None:
    a = square(0, 0, 1)
    b = square(5, 0, 1, clockwise=True)
    assert quad_distance(a, b) == pytest.approx(3.0, abs=ABS)
    assert quad_distance(b, a) == pytest.approx(3.0, abs=ABS)


def test_rotated_quad_distance() -> None:
    q = rotated_square(0.5, 45)  # diamond with half-diagonal sqrt(2)/2
    s = Segment((2, -3), (2, 3))
    assert segment_quad_distance(s, q) == pytest.approx(2 - math.sqrt(2) / 2, abs=ABS)


def test_degenerate_quads() -> None:
    flat = Quad(((0, 0), (10, 0), (10, 0), (0, 0)))
    far = Segment((50, 0), (60, 0))
    assert segment_quad_distance(far, flat) == pytest.approx(40.0, abs=ABS)
    assert segment_quad_distance(Segment((5, -1), (5, 1)), flat) == 0.0
    point = Quad(((1, 1), (1, 1), (1, 1), (1, 1)))
    assert quad_distance(point, square(4, 1, 1)) == pytest.approx(2.0, abs=ABS)
    assert quad_distance(point, point) == 0.0


def test_polygon_segments_drops_zero_length() -> None:
    pts: list[Vec] = [(0, 0), (0, 0), (1, 0), (1, 1)]
    assert polygon_segments(pts, closed=False) == (
        Segment((0, 0), (1, 0)),
        Segment((1, 0), (1, 1)),
    )
    closed = polygon_segments(pts, closed=True)
    assert closed[-1] == Segment((1, 1), (0, 0))
    assert len(closed) == len(pts) - 1


def test_polygon_segments_repeated_point() -> None:
    assert polygon_segments([(2, 2), (2, 2), (2, 2)], closed=False) == ()
    assert polygon_segments([(2, 2)], closed=True) == ()
    assert polygon_segments([], closed=True) == ()


def test_tessellate_quarter_circle() -> None:
    pts = tessellate_arc((0, 0), 10, 0, 90)
    assert pts[0] == (10.0, 0.0)
    assert pts[-1] == pytest.approx((0.0, 10.0), abs=1e-12)
    assert len(pts) > len(((0, 0), (1, 1)))
    for (x0, y0), (x1, y1) in itertools.pairwise(pts):
        mid = math.hypot((x0 + x1) / 2, (y0 + y1) / 2)
        assert 10 - mid <= 0.02 + 1e-12
    for x, y in pts:
        assert math.hypot(x, y) == pytest.approx(10.0, abs=1e-9)


def test_tessellate_wraps() -> None:
    pts = tessellate_arc((0, 0), 10, 350, 10)
    angles = [math.degrees(math.atan2(y, x)) for x, y in pts]
    assert angles[0] == pytest.approx(-10.0, abs=1e-9)
    assert angles[-1] == pytest.approx(10.0, abs=1e-9)
    assert all(-10.0 - 1e-9 <= a <= 10.0 + 1e-9 for a in angles)


def test_tessellate_degenerate_arc() -> None:
    pts = tessellate_arc((1, 2), 5, 30, 30)
    assert len(pts) == 1
    assert pts[0] == pytest.approx((1 + 5 * math.cos(math.radians(30)), 2 + 2.5), abs=ABS)


def test_tessellate_tiny_radius_and_large_error() -> None:
    # error budget larger than the radius: the ratio is clamped, one chord per half turn at most
    pts = tessellate_arc((0, 0), 0.01, 0, 180)
    assert len(pts) in {2, 3}
    assert pts[0] == (0.01, 0.0)


def test_tessellate_has_n_plus_one_points() -> None:
    r, e, sweep = 10.0, 0.02, 90.0
    n = math.ceil(math.radians(sweep) / (2 * math.acos(1 - e / r)))
    assert len(tessellate_arc((0, 0), r, 0, sweep, e)) == n + 1


def test_inflate_quad() -> None:
    inflated = inflate_quad(square(0, 0, 1), 0.5)
    xs = sorted(x for x, _ in inflated.corners)
    ys = sorted(y for _, y in inflated.corners)
    assert xs == pytest.approx([-1.5, -1.5, 1.5, 1.5], abs=ABS)
    assert ys == pytest.approx([-1.5, -1.5, 1.5, 1.5], abs=ABS)


def test_inflate_quad_clockwise_and_rotated() -> None:
    cw = inflate_quad(square(0, 0, 1, clockwise=True), 0.5)
    assert quad_distance(cw, square(5, 0, 1)) == pytest.approx(5 - 1 - 1.5, abs=ABS)
    rotated = inflate_quad(rotated_square(1, 30), 0.25)
    # each side moved by exactly 0.25: the side-to-side width grew from 2 to 2.5
    (a, b, c, _) = rotated.corners
    assert math.dist(a, b) == pytest.approx(2.5, abs=ABS)
    assert math.dist(b, c) == pytest.approx(2.5, abs=ABS)


def test_inflate_degenerate_quads() -> None:
    flat = inflate_quad(Quad(((0, 0), (10, 0), (10, 0), (0, 0))), 0.2)
    xs = [x for x, _ in flat.corners]
    ys = [y for _, y in flat.corners]
    assert (min(xs), max(xs)) == pytest.approx((-0.2, 10.2), abs=ABS)
    assert (min(ys), max(ys)) == pytest.approx((-0.2, 0.2), abs=ABS)
    dot = inflate_quad(Quad(((1, 1), (1, 1), (1, 1), (1, 1))), 0.5)
    assert aabb(dot.corners) == pytest.approx((0.5, 0.5, 1.5, 1.5), abs=ABS)


def test_inflate_zero_distance_is_identity_for_rectangles() -> None:
    q = rotated_square(1, 20)
    inflated = inflate_quad(q, 0.0)
    for got, want in zip(inflated.corners, q.corners, strict=True):
        assert got == pytest.approx(want, abs=ABS)


def test_aabb() -> None:
    assert aabb([(1, 5), (-2, 3), (4, -1)]) == (-2, -1, 4, 5)


@pytest.mark.parametrize(("start", "end"), [(0, 360), (-180, 180), (90, 810), (360, 0)])
def test_tessellate_full_circle(start: float, end: float) -> None:
    pts = tessellate_arc((0, 0), 10, start, end)
    assert len(pts) > len(((0, 0), (1, 1), (2, 2)))
    assert pts[0] == pytest.approx(pts[-1], abs=1e-9)
    for x, y in pts:
        assert math.hypot(x, y) == pytest.approx(10.0, abs=1e-9)
    for (x0, y0), (x1, y1) in itertools.pairwise(pts):
        assert 10 - math.hypot((x0 + x1) / 2, (y0 + y1) / 2) <= 0.02 + 1e-12


def test_tessellate_zero_length_arc() -> None:
    assert len(tessellate_arc((0, 0), 10, 30, 30)) == 1
    assert len(tessellate_arc((0, 0), 10, -90, -90)) == 1


def test_closest_points() -> None:
    cross = closest_points(Segment((0, 0), (2, 2)), Segment((0, 2), (2, 0)))
    assert cross[0] == pytest.approx((1.0, 1.0), abs=ABS)
    assert cross[1] == cross[0]
    a, b = closest_points(Segment((0, 0), (10, 0)), Segment((3, 4), (3, 9)))
    assert a == pytest.approx((3.0, 0.0), abs=ABS)
    assert b == pytest.approx((3.0, 4.0), abs=ABS)
    p, q = closest_points(Segment((1, 1), (1, 1)), Segment((4, 5), (4, 5)))
    assert (p, q) == ((1, 1), (4, 5))


def test_point_in_polygon_convex_and_boundary() -> None:
    sq = square(0, 0, 1).corners
    assert point_in_polygon((0, 0), sq)
    assert point_in_polygon((1, 0), sq)  # on the boundary
    assert point_in_polygon((0, 0), square(0, 0, 1, clockwise=True).corners)
    assert not point_in_polygon((1.1, 0), sq)


def test_point_in_polygon_triangle_pentagon_and_concave() -> None:
    triangle = ((0.0, 0.0), (10.0, 5.0), (10.0, -5.0))
    assert point_in_polygon((5, 0.5), triangle)
    assert not point_in_polygon((5, 3), triangle)
    assert point_in_polygon((5, 0.5), triangle[::-1])
    pentagon = ((0.0, 0.0), (4.0, -3.0), (8.0, 0.0), (6.0, 4.0), (2.0, 4.0))
    assert point_in_polygon((4, 1), pentagon)
    assert not point_in_polygon((-1, 1), pentagon)
    dart = ((0.0, 0.0), (10.0, 4.0), (7.0, 0.0), (10.0, -4.0))  # concave notch at the back
    assert point_in_polygon((5, 0.1), dart)
    assert not point_in_polygon((9, 0), dart)


@pytest.mark.parametrize(
    ("start", "end", "sweep"),
    [
        (0.0, 90.0, 90.0),
        (350.0, 10.0, 20.0),
        (0.0, 360.0, 360.0),
        (30.0, 30.0, 0.0),
        (30.0, 30.0 - 1e-13, 0.0),
        (30.0, 30.0 + 1e-7, 0.0),
        (30.0, 30.0 + 3e-6, 3e-6),
        (109.14694036038935, 469.1469403603894, 360.0),
        (0.0, 360.0 - 1e-7, 360.0),
        (-90.0, 270.0 + 1e-13, 360.0),
        (0.0, -360.0, 360.0),
    ],
)
def test_arc_sweep_uses_angle_quantum_tolerance(start: float, end: float, sweep: float) -> None:
    assert arc_sweep_deg(start, end) == pytest.approx(sweep, abs=1e-5)


def test_tessellate_radians_roundtrip_is_a_full_circle() -> None:
    start, end = 109.14694036038935, 469.1469403603894  # degrees(a), degrees(a + 2 pi)
    assert end - start != FULL_TURN  # float noise, the reason for the tolerance
    pts = tessellate_arc((0, 0), 10, start, end)
    assert len(pts) > len(((0, 0), (1, 1), (2, 2)))
    assert pts[0] == pytest.approx(pts[-1], abs=1e-9)


def test_tessellate_end_just_below_start_is_zero_length() -> None:
    assert len(tessellate_arc((0, 0), 10, 30, 30 - 1e-13)) == 1


def test_crossing_point() -> None:
    x = crossing_point(Segment((0, 0), (2, 2)), Segment((0, 2), (2, 0)))
    assert x == pytest.approx((1.0, 1.0), abs=ABS)
    assert crossing_point(Segment((0, 0), (2, 0)), Segment((1, 0), (1, 5))) is None  # T touch
    assert crossing_point(Segment((0, 0), (1, 0)), Segment((0, 1), (1, 1))) is None


def test_segment_contacts_crossing_endpoints_and_overlap() -> None:
    eps = 0.01
    cross = segment_contacts(Segment((0, 0), (2, 2)), Segment((0, 2), (2, 0)), eps)
    assert len(cross) == 1
    assert cross[0][0] == pytest.approx((1.0, 1.0), abs=ABS)
    assert cross[0][1] == cross[0][0]
    # collinear overlap [8, 10]: the contacts are the two ends of the overlap
    overlap = segment_contacts(Segment((0, 0), (10, 0)), Segment((8, 0), (20, 0)), eps)
    assert sorted({p for pair in overlap for p in pair}) == [(8.0, 0.0), (10.0, 0.0)]
    # T touch and a near miss within eps
    assert segment_contacts(Segment((0, 0), (10, 0)), Segment((5, 0.005), (5, 9)), eps) == (
        ((5.0, 0.0), (5.0, 0.005)),
    )
    assert segment_contacts(Segment((0, 0), (10, 0)), Segment((0, 1), (10, 1)), eps) == ()
