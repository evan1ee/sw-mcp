"""D3: text over model edges (spec 11.5.2)."""

from typing import TYPE_CHECKING

import pytest
from cad_drawing.checks.d3 import check_d3
from cad_drawing.checks.failures import CheckFailure, CheckItem
from cad_drawing.checks.primitives import sheet_primitives
from cad_drawing.checks.snapshot import Annotation, AnnotationKind, EdgeKind, View
from cad_drawing.checks.thresholds import CheckThresholds

if TYPE_CHECKING:
    from conftest import Builder

T = CheckThresholds()
EDGE = T.edge_clearance_mm


def run(b: "Builder", view: View, *annotations: Annotation) -> tuple[CheckFailure, ...]:
    sheet = b.sheet(annotations, [view])
    return check_d3(sheet, sheet_primitives(sheet, T), T)


def test_d3_text_over_edge(b: "Builder") -> None:
    view = b.view(
        "v1", [(b.line((0, 5), (30, 5)), "visible"), (b.line((0, 50), (30, 50)), "visible")]
    )
    note = b.annotation("n", kind="note", text_boxes=[b.box(5, 5.1, 15, 7, method="font_metrics")])
    (f,) = run(b, view, note)
    assert f.check == "D3"
    assert f.items == (CheckItem("annotation", "n"), CheckItem("edge", "v1", 0))
    assert f.methods == ("font_metrics", None)
    assert f.threshold_mm == EDGE
    assert f.distance_mm == pytest.approx(0.0, abs=1e-6)  # inflated by 0.2: reaches the edge


@pytest.mark.parametrize(("delta", "fails"), [(-1e-5, True), (0.0, False), (1e-5, False)])
def test_d3_threshold_boundary(b: "Builder", delta: float, fails: bool) -> None:
    view = b.view("v1", [(b.line((0, 5), (30, 5)), "visible")])
    note = b.annotation("n", text_boxes=[b.box(5, 5 + EDGE + delta, 15, 8)])
    assert (len(run(b, view, note)) == 1) is fails


@pytest.mark.parametrize("kind", ["visible", "silhouette", "hidden", "centerline", "center_mark"])
def test_d3_every_exported_edge_kind_counts(b: "Builder", kind: EdgeKind) -> None:
    view = b.view("v1", [(b.line((0, 5), (30, 5)), kind)])
    note = b.annotation("n", text_boxes=[b.box(5, 4, 15, 6)])
    assert len(run(b, view, note)) == 1


def test_d3_hidden_edge_counts_when_exported(b: "Builder") -> None:
    shown = b.view("v1", [(b.line((0, 5), (30, 5)), "hidden")])
    note = b.annotation("n", text_boxes=[b.box(5, 5.1, 15, 8)])
    assert len(run(b, shown, note)) == 1
    not_exported = b.view("v1", [])
    assert run(b, not_exported, note) == ()


def test_d3_dimension_line_over_edge_not_d3(b: "Builder") -> None:
    view = b.view("v1", [(b.line((0, 5), (30, 5)), "visible")])
    dim = b.annotation("d", dimension_lines=[b.line((0, 5), (30, 5))])
    assert run(b, view, dim) == ()


def test_d3_arc_edge_and_minimum_per_edge(b: "Builder") -> None:
    view = b.view("v1", [(b.arc((0, 0), 10, 0, 360), "visible")])
    note = b.annotation("n", text_boxes=[b.box(9.9, -1, 12, 1), b.box(9.95, 3, 12, 4)])
    (f,) = run(b, view, note)
    assert f.items == (CheckItem("annotation", "n"), CheckItem("edge", "v1", 0))
    assert f.distance_mm < EDGE


def test_d3_text_over_full_circle_written_through_radians(b: "Builder") -> None:
    start, end = 109.14694036038935, 469.1469403603894  # degrees(a), degrees(a + 2 pi)
    view = b.view("v1", [(b.arc((0, 0), 10, start, end), "visible")])
    note = b.annotation("n", text_boxes=[b.box(-11, -1, -9, 1)])
    (f,) = run(b, view, note)
    assert f.items == (CheckItem("annotation", "n"), CheckItem("edge", "v1", 0))


@pytest.mark.parametrize("kind", ["center_mark", "centerline"])
def test_d3_center_mark_and_centerline_annotation_lines_count_as_edges(
    b: "Builder", kind: AnnotationKind
) -> None:
    line = b.annotation("c", kind=kind, dimension_lines=[b.line((0, 5), (30, 5))])
    note = b.annotation("n", text_boxes=[b.box(5, 4, 15, 6)])
    sheet = b.sheet([line, note])
    (f,) = check_d3(sheet, sheet_primitives(sheet, T), T)
    assert f.items == (CheckItem("annotation", "c"), CheckItem("annotation", "n"))
    assert f.distance_mm == 0.0


def test_d3_leader_of_a_center_mark_counts_and_own_text_does_not(b: "Builder") -> None:
    mark = b.annotation(
        "c", kind="center_mark", leaders=[[(0, 5), (30, 5)]], text_boxes=[b.box(5, 4, 15, 6)]
    )
    note = b.annotation("n", text_boxes=[b.box(20, 4, 25, 6)])
    sheet = b.sheet([mark, note])
    (f,) = check_d3(sheet, sheet_primitives(sheet, T), T)
    assert f.items == (CheckItem("annotation", "c"), CheckItem("annotation", "n"))
