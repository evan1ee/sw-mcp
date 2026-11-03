"""D7: geometry inside the border and clear of the title block (plan Task 6)."""

from typing import TYPE_CHECKING

import pytest
from cad_drawing.checks.d7 import check_d7
from cad_drawing.checks.failures import CheckFailure, CheckItem
from cad_drawing.checks.primitives import sheet_primitives
from cad_drawing.checks.snapshot import Annotation, Rect, Sheet, View
from cad_drawing.checks.thresholds import CheckThresholds

if TYPE_CHECKING:
    from conftest import Builder

T = CheckThresholds()
EPS = T.epsilon_mm
TITLE = Rect((212.0, 5.0), (292.0, 45.0))
BORDER_MAX_X = 292.0


def run(
    b: "Builder", annotations: tuple[Annotation, ...] = (), views: tuple[View, ...] = ()
) -> tuple[CheckFailure, ...]:
    sheet: Sheet = b.sheet(annotations, views, title_block=[TITLE])
    return check_d7(sheet, sheet_primitives(sheet, T), T)


def test_d7_annotation_outside_border(b: "Builder") -> None:
    note = b.annotation(
        "n",
        kind="note",
        text_boxes=[b.box(280, 100, 300, 103)],
        dimension_lines=[b.line((100, 100), (310, 100))],
    )
    (f,) = run(b, (note,))
    assert f.check == "D7"
    assert f.items == (CheckItem("annotation", "n"),)
    assert f.distance_mm == pytest.approx(310 - BORDER_MAX_X, abs=1e-6)
    assert f.threshold_mm == EPS
    assert f.methods == (None,)  # the farthest vertex belongs to the dimension line
    assert f.location == (310.0, 100.0)


def test_d7_text_method_reported(b: "Builder") -> None:
    note = b.annotation("n", text_boxes=[b.box(280, 100, 300, 103, method="font_metrics")])
    (f,) = run(b, (note,))
    assert f.methods == ("font_metrics",)


@pytest.mark.parametrize(("out", "fails"), [(0.005, False), (0.0099, False), (0.0101, True)])
def test_d7_epsilon_slack_at_border(b: "Builder", out: float, fails: bool) -> None:
    note = b.annotation("n", dimension_lines=[b.line((100, 100), (BORDER_MAX_X + out, 100))])
    assert (len(run(b, (note,))) == 1) is fails


def test_d7_view_over_title_block(b: "Builder") -> None:
    view = b.view("v1", outline=Rect((200.0, 30.0), (230.0, 60.0)))
    (f,) = run(b, views=(view,))
    assert f.items == (CheckItem("view", "v1"),)
    assert f.distance_mm == 0.0
    assert f.threshold_mm == EPS


def test_d7_view_outside_border(b: "Builder") -> None:
    view = b.view("v1", outline=Rect((0.0, 100.0), (40.0, 150.0)))
    (f,) = run(b, views=(view,))
    assert f.distance_mm == pytest.approx(10.0, abs=1e-6)


def test_d7_title_block_clearance_boundary(b: "Builder") -> None:
    def note_at(gap: float) -> Annotation:
        return b.annotation("n", text_boxes=[b.box(150, 20, TITLE.min[0] - gap, 25)])

    assert len(run(b, (note_at(EPS - 1e-5),))) == 1
    assert run(b, (note_at(EPS + 1e-5),)) == ()


def test_d7_annotation_over_title_block_has_zero_distance(b: "Builder") -> None:
    ann = b.annotation("n", dimension_lines=[b.line((150, 20), (260, 20))])
    (f,) = run(b, (ann,))
    assert f.items == (CheckItem("annotation", "n"),)
    assert f.distance_mm == 0.0


def test_d7_inside_ok_and_edges_ignored(b: "Builder") -> None:
    ok = b.annotation(
        "ok", text_boxes=[b.box(20, 20, 40, 25)], dimension_lines=[b.line((20, 30), (60, 30))]
    )
    view = b.view("v1", [(b.line((-50, 100), (500, 100)), "visible")])
    assert run(b, (ok,), (view,)) == ()


def test_d7_one_failure_per_item(b: "Builder") -> None:
    ann = b.annotation(
        "n",
        dimension_lines=[b.line((0, 0), (400, 400))],
        extension_lines=[b.ext("e", (-5, 100), (500, 100))],
    )
    assert len(run(b, (ann,))) == 1


def test_d7_arc_bulging_past_the_border_between_vertices_fails(b: "Builder") -> None:
    # The apex of the arc lies 0.015 mm above the border; only the tessellation can show it.
    arc = b.annotation("a", dimension_lines=[b.arc((150, 205 - 50 + 0.015), 50, 60, 120)])
    (f,) = run(b, (arc,))
    assert f.items == (CheckItem("annotation", "a"),)
    assert f.distance_mm > EPS


def test_d7_centerline_annotation_line_work_is_checked(b: "Builder") -> None:
    mark = b.annotation("m", kind="center_mark", dimension_lines=[b.line((100, 100), (310, 100))])
    (f,) = run(b, (mark,))
    assert f.items == (CheckItem("annotation", "m"),)
    assert f.distance_mm == pytest.approx(310 - BORDER_MAX_X, abs=1e-6)
