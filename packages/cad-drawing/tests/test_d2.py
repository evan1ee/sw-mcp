"""D2: text overlap (spec 11.5.2)."""

import math
from typing import TYPE_CHECKING

import pytest
from cad_drawing.checks.d2 import check_d2
from cad_drawing.checks.failures import CheckFailure
from cad_drawing.checks.primitives import sheet_primitives
from cad_drawing.checks.snapshot import Annotation
from cad_drawing.checks.thresholds import CheckThresholds

if TYPE_CHECKING:
    from conftest import Builder

T = CheckThresholds()
TEXT = T.text_clearance_mm
LINE = T.line_clearance_mm
GAP = 0.3


def run(b: "Builder", *annotations: Annotation) -> tuple[CheckFailure, ...]:
    sheet = b.sheet(annotations)
    return check_d2(sheet, sheet_primitives(sheet, T), T)


def test_d2_text_boxes_too_close(b: "Builder") -> None:
    a = b.annotation("a", text_boxes=[b.box(0, 0, 10, 2)])
    c = b.annotation("c", text_boxes=[b.box(10 + GAP, 0, 20, 2, method="font_metrics")])
    (f,) = run(b, a, c)
    assert f.check == "D2"
    assert [i.id for i in f.items] == ["a", "c"]
    assert f.distance_mm == pytest.approx(GAP - 0.2, abs=1e-6)  # font-metric margin 0.1 x height 2
    assert f.threshold_mm == TEXT
    assert f.methods == ("display_data", "font_metrics")


@pytest.mark.parametrize(("delta", "fails"), [(-1e-5, True), (0.0, False), (1e-5, False)])
def test_d2_threshold_boundary(b: "Builder", delta: float, fails: bool) -> None:
    a = b.annotation("a", text_boxes=[b.box(0, 0, 10, 2)])
    c = b.annotation("c", text_boxes=[b.box(10 + TEXT + delta, 0, 20, 2)])
    assert (len(run(b, a, c)) == 1) is fails
    line_a = b.annotation("l", dimension_lines=[b.line((10 + LINE + delta, 1), (20, 1))])
    assert (len(run(b, a, line_a)) == 1) is fails


def test_d2_text_vs_other_dimension_line(b: "Builder") -> None:
    a = b.annotation("a", text_boxes=[b.box(0, 0, 10, 2)])
    near = b.annotation("n", dimension_lines=[b.line((0, 2.2), (10, 2.2))])
    (f,) = run(b, a, near)
    assert f.threshold_mm == LINE
    assert f.distance_mm == pytest.approx(0.2, abs=1e-6)
    assert f.methods == ("display_data", None)
    ext = b.annotation("e", extension_lines=[b.ext("e1", (5, 2.1), (5, 9))])
    arrow = b.annotation("w", arrowheads=[[(5, 2.1), (6, 5), (4, 5)]])
    assert len(run(b, a, ext)) == 1
    assert len(run(b, a, arrow)) == 1
    far = b.annotation("f", dimension_lines=[b.line((0, 2.5), (10, 2.5))])
    assert run(b, a, far) == ()


def test_d2_own_lines_ignored(b: "Builder") -> None:
    a = b.annotation(
        "a",
        text_boxes=[b.box(0, 0, 10, 2)],
        dimension_lines=[b.line((0, 1), (10, 1))],
        extension_lines=[b.ext("e1", (5, -1), (5, 3))],
    )
    assert run(b, a) == ()


def test_d2_text_over_line_inside_box(b: "Builder") -> None:
    a = b.annotation("a", text_boxes=[b.box(0, 0, 10, 2)])
    c = b.annotation("c", dimension_lines=[b.line((3, 0.5), (6, 1.5))])
    (f,) = run(b, a, c)
    assert f.distance_mm == 0.0


@pytest.mark.parametrize(("gap", "fails"), [(0.3, True), (0.7, False)])
def test_d2_rotated_boxes(b: "Builder", gap: float, fails: bool) -> None:
    deg = 30.0
    w = 10.0
    dx, dy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    a = b.annotation("a", text_boxes=[b.rotated_box(0, 0, w, 2, deg)])
    shift = w + gap
    c = b.annotation("c", text_boxes=[b.rotated_box(shift * dx, shift * dy, w, 2, deg)])
    result = run(b, a, c)
    assert (len(result) == 1) is fails
    if fails:
        assert result[0].distance_mm == pytest.approx(gap, abs=1e-6)


def test_d2_font_metric_margin_changes_verdict(b: "Builder") -> None:
    metric_a = b.box(0, 0, 10, 2, method="font_metrics", height=2)
    metric_c = b.box(10.55, 0, 20, 2, method="font_metrics", height=2)
    shown_a = b.box(0, 0, 10, 2)
    shown_c = b.box(10.55, 0, 20, 2)
    est = run(b, b.annotation("a", text_boxes=[metric_a]), b.annotation("c", text_boxes=[metric_c]))
    shown = run(b, b.annotation("a", text_boxes=[shown_a]), b.annotation("c", text_boxes=[shown_c]))
    assert len(est) == 1
    assert est[0].distance_mm == pytest.approx(0.15, abs=1e-6)
    assert est[0].methods == ("font_metrics", "font_metrics")
    assert shown == ()


def test_d2_minimum_per_owner_pair_and_both_classes(b: "Builder") -> None:
    a = b.annotation("a", text_boxes=[b.box(0, 0, 10, 2), b.box(0, 5, 10, 7)])
    c = b.annotation(
        "c",
        text_boxes=[b.box(10.4, 0, 20, 2), b.box(10.1, 5, 20, 7)],
        dimension_lines=[b.line((0, 2.1), (10, 2.1))],
    )
    result = run(b, a, c)
    assert [(f.threshold_mm, f.distance_mm) for f in result] == [
        (LINE, pytest.approx(0.1, abs=1e-6)),
        (TEXT, pytest.approx(0.1, abs=1e-6)),
    ]


def test_d2_center_mark_line_work_is_not_a_dimension_line(b: "Builder") -> None:
    note = b.annotation("n", text_boxes=[b.box(5, 4, 15, 6)])
    mark = b.annotation("c", kind="center_mark", dimension_lines=[b.line((0, 5), (30, 5))])
    assert run(b, note, mark) == ()
    plain = b.annotation("c", dimension_lines=[b.line((0, 5), (30, 5))])
    assert len(run(b, note, plain)) == 1
