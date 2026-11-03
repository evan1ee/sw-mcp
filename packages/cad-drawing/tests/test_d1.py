"""D1: crossing dimensions (spec 11.5.2)."""

import math
from typing import TYPE_CHECKING

import pytest
from cad_drawing.checks.d1 import check_d1
from cad_drawing.checks.failures import CheckFailure, CheckItem
from cad_drawing.checks.geometry2d import Vec, tessellate_arc
from cad_drawing.checks.primitives import sheet_primitives
from cad_drawing.checks.snapshot import Annotation
from cad_drawing.checks.thresholds import CheckThresholds

if TYPE_CHECKING:
    from conftest import Builder

T = CheckThresholds()
EPS = T.epsilon_mm


def run(b: "Builder", *annotations: Annotation) -> tuple[CheckFailure, ...]:
    sheet = b.sheet(annotations)
    return check_d1(sheet, sheet_primitives(sheet, T), T)


def items(f: CheckFailure) -> tuple[tuple[str, str], ...]:
    return tuple((i.kind, i.id) for i in f.items)


def test_d1_crossing_dimension_lines(b: "Builder") -> None:
    a = b.annotation("a", dimension_lines=[b.line((0, 0), (20, 20))])
    c = b.annotation("c", dimension_lines=[b.line((0, 20), (20, 0))])
    (f,) = run(b, a, c)
    assert f.check == "D1"
    assert f.sheet == "s_0"
    assert items(f) == (("annotation", "a"), ("annotation", "c"))
    assert f.distance_mm == 0.0
    assert f.threshold_mm == EPS
    assert f.location == pytest.approx((10.0, 10.0), abs=1e-6)
    assert f.methods == (None, None)


def test_d1_dimension_line_crosses_other_extension(b: "Builder") -> None:
    a = b.annotation("a", dimension_lines=[b.line((0, 5), (20, 5))])
    c = b.annotation("c", extension_lines=[b.ext("e1", (10, 0), (10, 10))])
    (f,) = run(b, a, c)
    assert items(f) == (("annotation", "a"), ("annotation", "c"))


def test_d1_arrowhead_on_other_extension_line(b: "Builder") -> None:
    a = b.annotation("a", arrowheads=[[(10, 5), (13, 6), (13, 4)]])
    c = b.annotation("c", extension_lines=[b.ext("e1", (10, 0), (10, 10))])
    assert len(run(b, a, c)) == 1


def test_d1_touching_and_collinear(b: "Builder") -> None:
    touch = run(
        b,
        b.annotation("a", dimension_lines=[b.line((0, 0), (10, 0))]),
        b.annotation("c", dimension_lines=[b.line((10, 0), (10, 10))]),
    )
    assert [f.distance_mm for f in touch] == [0.0]
    overlap = run(
        b,
        b.annotation("a", dimension_lines=[b.line((0, 0), (10, 0))]),
        b.annotation("c", dimension_lines=[b.line((5, 0), (15, 0))]),
    )
    assert [f.distance_mm for f in overlap] == [0.0]
    gap = run(
        b,
        b.annotation("a", dimension_lines=[b.line((0, 0), (10, 0))]),
        b.annotation("c", dimension_lines=[b.line((12, 0), (15, 0))]),
    )
    assert gap == ()


@pytest.mark.parametrize(("delta", "fails"), [(-1e-5, True), (0.0, True), (1e-5, False)])
def test_d1_epsilon_boundary(b: "Builder", delta: float, fails: bool) -> None:
    gap = EPS + delta
    a = b.annotation("a", dimension_lines=[b.line((0, 0), (10, 0))])
    c = b.annotation("c", dimension_lines=[b.line((0, gap), (10, gap))])
    result = run(b, a, c)
    assert (len(result) == 1) is fails
    if fails:
        assert result[0].distance_mm == pytest.approx(EPS, abs=2e-5)


def test_d1_same_dimension_ignored(b: "Builder") -> None:
    a = b.annotation(
        "a",
        dimension_lines=[b.line((0, 0), (20, 20)), b.line((0, 20), (20, 0))],
        extension_lines=[b.ext("e1", (10, 0), (10, 20))],
        arrowheads=[[(0, 0), (1, 0), (0, 1)]],
    )
    assert run(b, a) == ()


def test_d1_shared_extension_chain_ok(b: "Builder") -> None:
    # Baseline arrangement: both dimensions attach to e1; the longer extension line of "c" passes
    # through the end of the dimension line of "a" at (0, 5).
    a = b.annotation(
        "a",
        dimension_lines=[b.line((0, 5), (10, 5))],
        extension_lines=[b.ext("e1", (0, 0), (0, 6)), b.ext("e2", (10, 0), (10, 6))],
    )
    c = b.annotation(
        "c",
        dimension_lines=[b.line((0, 9), (20, 9))],
        extension_lines=[b.ext("e1", (0, 0), (0, 10)), b.ext("e3", (20, 0), (20, 10))],
    )
    assert run(b, a, c) == ()
    # The same layout with different entities is a real crossing.
    c_other = b.annotation(
        "c",
        dimension_lines=[b.line((0, 9), (20, 9))],
        extension_lines=[b.ext("e9", (0, 0), (0, 10)), b.ext("e3", (20, 0), (20, 10))],
    )
    assert len(run(b, a, c_other)) == 1


def _chain(b: "Builder", *, stray: bool = False) -> tuple[Annotation, Annotation, Annotation]:
    """Three dimensions in a row; e2 is shared by a/b and e3 by b/c."""
    a = b.annotation(
        "a",
        dimension_lines=[b.line((0, 5), (10, 5))],
        extension_lines=[b.ext("e1", (0, 0), (0, 8)), b.ext("e2", (10, 0), (10, 8))],
        arrowheads=[[(0, 5), (2, 6), (2, 4)], [(10, 5), (8, 6), (8, 4)]],
    )
    b_lines = [b.line((10, 5), (20, 5))]
    if stray:
        b_lines.append(b.line((4, 0), (4, 10)))
    mid = b.annotation(
        "b",
        dimension_lines=b_lines,
        extension_lines=[b.ext("e2", (10, 0), (10, 8)), b.ext("e3", (20, 0), (20, 8))],
        arrowheads=[[(10, 5), (12, 6), (12, 4)], [(20, 5), (18, 6), (18, 4)]],
    )
    c = b.annotation(
        "c",
        dimension_lines=[b.line((20, 5), (30, 5))],
        extension_lines=[b.ext("e3", (20, 0), (20, 8)), b.ext("e4", (30, 0), (30, 8))],
        arrowheads=[[(20, 5), (22, 6), (22, 4)], [(30, 5), (28, 6), (28, 4)]],
    )
    return a, mid, c


def test_d1_chain_contacts_at_shared_extension_ok(b: "Builder") -> None:
    assert run(b, *_chain(b)) == ()


def test_d1_chain_crossing_away_from_shared_line_fails(b: "Builder") -> None:
    (f,) = run(b, *_chain(b, stray=True))
    assert items(f) == (("annotation", "a"), ("annotation", "b"))
    assert f.location == pytest.approx((4.0, 5.0), abs=1e-6)


def test_d1_touch_near_unshared_extension_fails(b: "Builder") -> None:
    a = b.annotation(
        "a",
        dimension_lines=[b.line((0, 5), (10, 5))],
        extension_lines=[b.ext("e1", (10, 0), (10, 8))],
    )
    c = b.annotation(
        "c",
        dimension_lines=[b.line((10, 5), (20, 5))],
        extension_lines=[b.ext("e9", (20, 0), (20, 8))],
    )
    # dimension line x dimension line, and c's line x a's (unshared) extension line.
    assert [f.distance_mm for f in run(b, a, c)] == [0.0, 0.0]


def test_d1_shared_entity_but_apart_is_not_coincident(b: "Builder") -> None:
    a = b.annotation(
        "a",
        dimension_lines=[b.line((0, 5), (10, 5))],
        extension_lines=[b.ext("e1", (50, 0), (50, 6))],
    )
    c = b.annotation("c", extension_lines=[b.ext("e1", (0, 0), (0, 10))])
    assert len(run(b, a, c)) == 1


def test_d1_extension_extension_not_failure(b: "Builder") -> None:
    a = b.annotation("a", extension_lines=[b.ext("e1", (0, 0), (0, 10))])
    c = b.annotation("c", extension_lines=[b.ext("e2", (-5, 5), (5, 5))])
    assert run(b, a, c) == ()


def test_d1_arc_dimension(b: "Builder") -> None:
    arc = b.annotation("ang", dimension_lines=[b.arc((0, 0), 20, 0, 90)])
    cross = b.annotation("c", dimension_lines=[b.line((0, 0), (30, 30))])
    (f,) = run(b, arc, cross)
    assert f.location == pytest.approx((14.142, 14.142), abs=0.05)
    far = b.annotation("d", dimension_lines=[b.line((0, 0), (5, 5))])
    assert run(b, arc, far) == ()


def test_d1_reports_minimum_over_segment_pairs(b: "Builder") -> None:
    a = b.annotation("a", dimension_lines=[b.line((0, 0), (10, 0), (10, 10))])
    c = b.annotation("c", dimension_lines=[b.line((-5, 5), (5, 5), (5, -5))])
    (f,) = run(b, a, c)
    assert f.distance_mm == 0.0
    assert f.location == pytest.approx((5.0, 0.0), abs=1e-6)


def test_d1_failures_are_deterministic_and_items_sorted(b: "Builder") -> None:
    a = b.annotation("zz", dimension_lines=[b.line((0, 0), (10, 10))])
    c = b.annotation("aa", dimension_lines=[b.line((0, 10), (10, 0))])
    (f1,) = run(b, a, c)
    (f2,) = run(b, c, a)
    assert f1 == f2
    assert items(f1) == (("annotation", "aa"), ("annotation", "zz"))
    assert CheckItem("annotation", "aa") == f1.items[0]


def _base(b: "Builder") -> Annotation:
    """Dimension "a" from e0 to e1, with its dimension line at y = 20."""
    return b.annotation(
        "a",
        dimension_lines=[b.line((0, 20), (10, 20))],
        extension_lines=[b.ext("e0", (0, 0), (0, 22)), b.ext("e1", (10, 0), (10, 22))],
    )


@pytest.mark.parametrize("line", [((8, 20), (20, 20)), ((20, 20), (8, 20))])
def test_d1_overlap_past_shared_extension_fails(b: "Builder", line: tuple[Vec, Vec]) -> None:
    follower = b.annotation(
        "b",
        dimension_lines=[b.line(*line)],
        extension_lines=[b.ext("e1", (10, 0), (10, 22)), b.ext("e2", (20, 0), (20, 22))],
    )
    (f,) = run(b, _base(b), follower)
    assert items(f) == (("annotation", "a"), ("annotation", "b"))
    assert f.location == pytest.approx((8.0, 20.0), abs=1e-6)  # the end of the overlap [8, 10]


def test_d1_clean_chain_still_passes_with_contact_sets(b: "Builder") -> None:
    follower = b.annotation(
        "b",
        dimension_lines=[b.line((10, 20), (20, 20))],
        extension_lines=[b.ext("e1", (10, 0), (10, 22)), b.ext("e2", (20, 0), (20, 22))],
    )
    assert run(b, _base(b), follower) == ()


def _tall(b: "Builder") -> Annotation:
    return b.annotation(
        "a",
        dimension_lines=[b.line((0, 40), (10, 40))],
        extension_lines=[b.ext("e0", (0, 0), (0, 42)), b.ext("e1", (10, 0), (10, 42))],
    )


def _short_follower(b: "Builder", *, leader: bool) -> Annotation:
    crossing = [(5.0, 30.0), (15.0, 30.0)]
    return b.annotation(
        "b",
        dimension_lines=[b.line((10, 10), (20, 10))] + ([] if leader else [b.line(*crossing)]),
        leaders=[crossing] if leader else [],
        extension_lines=[b.ext("e1", (10, 0), (10, 12)), b.ext("e2", (20, 0), (20, 12))],
    )


@pytest.mark.parametrize("leader", [False, True])
def test_d1_line_crossing_shared_extension_beyond_own_fails(b: "Builder", leader: bool) -> None:
    (f,) = run(b, _tall(b), _short_follower(b, leader=leader))
    assert items(f) == (("annotation", "a"), ("annotation", "b"))
    assert f.location == pytest.approx((10.0, 30.0), abs=1e-6)


def test_d1_follower_within_overlap_of_extension_lines_passes(b: "Builder") -> None:
    ok = b.annotation(
        "b",
        dimension_lines=[b.line((10, 10), (20, 10))],
        extension_lines=[b.ext("e1", (10, 0), (10, 12)), b.ext("e2", (20, 0), (20, 12))],
    )
    assert run(b, _tall(b), ok) == ()


def test_d1_one_failure_per_owner_pair_and_class(b: "Builder") -> None:
    # Dimension lines cross twice and an arrowhead sits on the crossing: still one line failure.
    a = b.annotation(
        "a",
        dimension_lines=[b.line((0, 0), (10, 10)), b.line((0, 4), (10, 6))],
        arrowheads=[[(5, 5), (4, 5.5), (4.5, 4)]],
    )
    c = b.annotation("b", dimension_lines=[b.line((0, 10), (10, 0))])
    (f,) = run(b, a, c)
    assert f.distance_mm == 0.0
    # Each one's dimension line crosses the other's extension line: one extension failure.
    p = b.annotation(
        "p",
        dimension_lines=[b.line((0, 5), (20, 5))],
        extension_lines=[b.ext("e1", (30, 0), (30, 10))],
    )
    q = b.annotation(
        "q",
        dimension_lines=[b.line((30, 12), (40, 12)), b.line((25, 5), (35, 5))],
        extension_lines=[b.ext("e2", (10, 0), (10, 10))],
    )
    assert [items(x) for x in run(b, p, q)] == [(("annotation", "p"), ("annotation", "q"))]


def test_d1_straight_line_tangent_to_arc_at_chord_midpoint_fails(b: "Builder") -> None:
    r = 50.0
    n = len(tessellate_arc((0, 0), r, 0, 90, T.arc_chord_error_mm)) - 1
    mid = math.radians(90 / n / 2)
    tx, ty = r * math.cos(mid), r * math.sin(mid)  # on the true circle, tangent direction below
    dx, dy = -math.sin(mid), math.cos(mid)
    arc = b.annotation("a", dimension_lines=[b.arc((0, 0), r, 0, 90)])
    tangent = b.annotation("b", dimension_lines=[b.line((tx - dx, ty - dy), (tx + dx, ty + dy))])
    (f,) = run(b, arc, tangent)
    assert f.distance_mm <= EPS / 2 + 1e-9


@pytest.mark.parametrize(
    "polygon",
    [
        [(0, 0), (10, 5), (10, -5)],  # triangle
        [(0, 0), (4, -3), (8, 0), (6, 4), (2, 4)],  # pentagon
        [(0, 0), (10, 4), (7, 0), (10, -4)],  # concave dart
    ],
)
def test_d1_segment_inside_arrowhead_polygon_fails(b: "Builder", polygon: list[Vec]) -> None:
    head = b.annotation("a", arrowheads=[polygon])
    inside = b.annotation("b", dimension_lines=[b.line((4, 0.5), (4.5, 0.5))])
    (f,) = run(b, head, inside)
    assert f.distance_mm == 0.0


def test_d1_segment_in_the_notch_of_a_concave_arrowhead_passes(b: "Builder") -> None:
    dart = b.annotation("a", arrowheads=[[(0, 0), (10, 4), (7, 0), (10, -4)]])
    notch = b.annotation("b", dimension_lines=[b.line((9, -0.2), (9.5, 0.2))])
    assert run(b, dart, notch) == ()


def test_d1_nested_arrowheads_at_a_shared_extension_line_fail(b: "Builder") -> None:
    a = b.annotation(
        "a",
        dimension_lines=[b.line((0, 20), (10, 20))],
        arrowheads=[[(10, 20), (7.5, 20.5), (7.5, 19.5)]],
        extension_lines=[b.ext("e0", (0, 0), (0, 22)), b.ext("e1", (10, 0), (10, 22))],
    )
    c = b.annotation(
        "b",
        dimension_lines=[b.line((10, 20), (12, 20))],
        arrowheads=[[(10, 20), (7.6, 20.45), (7.6, 19.55)]],
        extension_lines=[b.ext("e1", (10, 0), (10, 22)), b.ext("e2", (12, 0), (12, 22))],
    )
    assert len(run(b, a, c)) == 1
