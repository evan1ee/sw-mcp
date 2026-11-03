"""Geometric soft metrics (spec 11.5, plan Task 6)."""

from typing import TYPE_CHECKING

from cad_drawing.checks.primitives import sheet_primitives
from cad_drawing.checks.snapshot import EdgeKind
from cad_drawing.checks.soft_metrics import SoftMetrics, compute_soft_metrics
from cad_drawing.checks.thresholds import CheckThresholds

if TYPE_CHECKING:
    from conftest import Builder

T = CheckThresholds()
VISIBLE_AND_SILHOUETTE = 2


def test_soft_extension_crossings_counted(b: "Builder") -> None:
    a = b.annotation(
        "a", extension_lines=[b.ext("e1", (0, 0), (0, 10)), b.ext("e2", (9, 0), (9, 4))]
    )
    c = b.annotation("c", extension_lines=[b.ext("e3", (-5, 5), (5, 5))])
    own = b.annotation(
        "d", extension_lines=[b.ext("e4", (0, 20), (0, 30)), b.ext("e5", (-1, 25), (1, 25))]
    )
    sheet = b.sheet([a, c, own])
    m = compute_soft_metrics(sheet, sheet_primitives(sheet, T), T)
    assert m == SoftMetrics(1, 0, 0, (297.0, 210.0))


def test_soft_dimension_lines_over_edges_counted_per_annotation_edge(b: "Builder") -> None:
    view = b.view(
        "v1", [(b.line((0, 5), (30, 5)), "visible"), (b.line((0, 50), (30, 50)), "hidden")]
    )
    over = b.annotation("a", dimension_lines=[b.line((10, 0), (10, 10)), b.line((20, 0), (20, 10))])
    clear = b.annotation("c", dimension_lines=[b.line((10, 20), (10, 30))])
    leader = b.annotation("l", leaders=[[(5, 0), (5, 9)]])
    sheet = b.sheet([over, clear, leader], [view])
    m = compute_soft_metrics(sheet, sheet_primitives(sheet, T), T)
    assert (m.dimension_lines_over_edges, m.view_count) == (2, 1)
    assert m.extension_crossings == 0


def test_soft_shared_extension_lines_of_a_chain_are_not_crossings(b: "Builder") -> None:
    first = b.annotation(
        "a",
        dimension_lines=[b.line((0, 20), (10, 20))],
        extension_lines=[b.ext("e0", (0, 0), (0, 22)), b.ext("e1", (10, 0), (10, 22))],
    )
    second = b.annotation(
        "b",
        dimension_lines=[b.line((10, 20), (20, 20))],
        extension_lines=[b.ext("e1", (10, 0), (10, 22)), b.ext("e2", (20, 0), (20, 22))],
    )
    sheet = b.sheet([first, second])
    assert compute_soft_metrics(sheet, sheet_primitives(sheet, T), T).extension_crossings == 0
    other = b.annotation("c", extension_lines=[b.ext("e9", (10, 0), (10, 22))])
    sheet = b.sheet([first, other])
    assert compute_soft_metrics(sheet, sheet_primitives(sheet, T), T).extension_crossings == 1


def test_soft_edges_over_count_only_visible_and_silhouette(b: "Builder") -> None:
    kinds: list[EdgeKind] = ["visible", "silhouette", "hidden", "centerline", "center_mark"]
    view = b.view(
        "v1", [(b.line((0, 5 + 10 * i), (30, 5 + 10 * i)), k) for i, k in enumerate(kinds)]
    )
    cross = b.annotation("a", dimension_lines=[b.line((10, 0), (10, 60))])
    mark = b.annotation("m", kind="centerline", dimension_lines=[b.line((20, 0), (20, 60))])
    sheet = b.sheet([cross, mark], [view])
    m = compute_soft_metrics(sheet, sheet_primitives(sheet, T), T)
    assert m.dimension_lines_over_edges == VISIBLE_AND_SILHOUETTE


def test_soft_leader_touching_the_edge_it_points_at_is_not_counted(b: "Builder") -> None:
    view = b.view("v1", [(b.line((60, 50), (60, 70)), "visible")])
    pointing = b.annotation("n", kind="note", leaders=[[(30, 30), (60, 60)]])
    reverse = b.annotation("r", kind="note", leaders=[[(60, 60), (30, 30)]])
    through = b.annotation("t", kind="note", leaders=[[(30, 30), (90, 90)]])
    line_end = b.annotation("d", dimension_lines=[b.line((30, 30), (60, 60))])
    for ann, expected in ((pointing, 0), (reverse, 0), (through, 1), (line_end, 1)):
        sheet = b.sheet([ann], [view])
        m = compute_soft_metrics(sheet, sheet_primitives(sheet, T), T)
        assert m.dimension_lines_over_edges == expected, ann.key
