"""D5 duplicates part: repeated parameters and closed chains (spec 11.5.3)."""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from cad_drawing.checks.d5 import check_d5
from cad_drawing.checks.snapshot import Annotation, Snapshot
from cad_drawing.checks.thresholds import CheckThresholds

if TYPE_CHECKING:
    from conftest import Builder

T = CheckThresholds()
THREE = 3
TWO = 2


def dim(  # noqa: PLR0913
    b: "Builder",
    key: str,
    entities: tuple[str, str],
    p0: tuple[float, float] = (0.0, 0.0),
    p1: tuple[float, float] = (10.0, 0.0),
    *,
    parameters: Sequence[str] | None = None,
    parenthesized: bool | None = False,
    view: str | None = "v_a",
) -> Annotation:
    return b.annotation(
        key,
        dimension_lines=[b.line(p0, p1)],
        extension_lines=[b.ext(entities[0], p0, p0), b.ext(entities[1], p1, p1)],
        parameters=(f"P_{key}@S",) if parameters is None else parameters,
        parenthesized=parenthesized,
        view=view,
    )


def snap(b: "Builder", *annotations: Annotation) -> Snapshot:
    return b.snapshot([b.sheet(annotations)])


def keys(failure_items: Sequence[object]) -> list[str]:
    return [getattr(i, "id") for i in failure_items]  # noqa: B009


def test_d5_duplicate_parameter(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            b.annotation("a1", parameters=["D1@Sketch1"], parenthesized=False),
            b.annotation("a2", parameters=["D1@Sketch1", "D2@Sketch1"], parenthesized=False),
        ),
        T,
    )
    assert out.status == "fail"
    assert dict(out.parts)["duplicates"] == "fail"
    (failure,) = out.failures
    assert failure.code == "duplicate_parameter"
    assert failure.sheet == "s_0"
    assert failure.detail == (("parameter", "D1@Sketch1"),)
    assert keys(failure.items) == ["a1", "a2"]


def test_d5_duplicate_across_sheets(b: "Builder") -> None:
    s0 = b.sheet([b.annotation("a1", parameters=["P"], parenthesized=False)], key="s_0")
    s1 = b.sheet([b.annotation("a2", parameters=["P"], parenthesized=False)], key="s_1", index=1)
    out = check_d5(b.snapshot([s0, s1]), T)
    (failure,) = out.failures
    assert failure.sheet is None
    assert [(i.id, i.sheet) for i in failure.items] == [("a1", "s_0"), ("a2", "s_1")]


def test_d5_parenthesized_duplicate_still_fails(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            b.annotation("a1", parameters=["P"], parenthesized=False),
            b.annotation("a2", parameters=["P"], parenthesized=True),
        ),
        T,
    )
    assert out.status == "fail"
    assert [f.code for f in out.failures] == ["duplicate_parameter"]


def test_d5_empty_parameters_is_read(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            b.annotation("a1", parameters=[], parenthesized=True),
            b.annotation("a2", parameters=[], parenthesized=True),
        ),
        T,
    )
    assert out.failures == ()
    assert dict(out.parts)["duplicates"] == "pass"
    assert out.reasons == ("drawing_intent_required",)


def test_d5_clean_is_not_evaluated_without_intent(b: "Builder") -> None:
    out = check_d5(snap(b, dim(b, "d1", ("a", "b"))), T)
    assert out.status == "not_evaluated"
    assert out.parts == (("auxiliary_marking", "not_evaluated"), ("duplicates", "pass"))
    assert out.reasons == ("drawing_intent_required",)
    assert out.failures == ()


def test_d5_missing_data_not_evaluated(b: "Builder") -> None:
    out = check_d5(snap(b, b.annotation("a1")), T)
    assert out.status == "not_evaluated"
    assert dict(out.parts)["duplicates"] == "not_evaluated"
    assert out.reasons == ("drawing_intent_required", "dimension_data_missing")

    note = check_d5(snap(b, b.annotation("n1", kind="note")), T)
    assert note.reasons == ("drawing_intent_required",)
    assert dict(note.parts)["duplicates"] == "pass"

    both = check_d5(
        snap(
            b,
            b.annotation("a1"),
            b.annotation("a2", parameters=["P"], parenthesized=False),
            b.annotation("a3", parameters=["P"], parenthesized=False),
        ),
        T,
    )
    assert both.status == "fail"
    assert both.reasons == ("drawing_intent_required",)


def test_d5_closed_chain(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            dim(b, "d1", ("a", "b")),
            dim(b, "d2", ("b", "c")),
            dim(b, "d3", ("a", "c")),
        ),
        T,
    )
    assert out.status == "fail"
    (failure,) = out.failures
    assert failure.code == "closed_chain"
    assert failure.detail == ()
    assert failure.sheet == "s_0"
    assert keys(failure.items) == ["d1", "d2", "d3"]


def test_d5_chain_with_parenthesized_is_open(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            dim(b, "d1", ("a", "b")),
            dim(b, "d2", ("b", "c")),
            dim(b, "d3", ("a", "c"), parenthesized=True),
        ),
        T,
    )
    assert out.failures == ()
    assert dict(out.parts)["duplicates"] == "pass"


def test_d5_two_parallel_same_entities(b: "Builder") -> None:
    out = check_d5(
        snap(b, dim(b, "d1", ("a", "b")), dim(b, "d2", ("a", "b"), (0.0, 5.0), (10.0, 5.0))),
        T,
    )
    (failure,) = out.failures
    assert failure.code == "closed_chain"
    assert keys(failure.items) == ["d1", "d2"]


def test_d5_open_chain_ok(b: "Builder") -> None:
    out = check_d5(snap(b, dim(b, "d1", ("a", "b")), dim(b, "d2", ("b", "c"))), T)
    assert out.failures == ()


def test_d5_chain_reversed_direction(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            dim(b, "d1", ("a", "b")),
            dim(b, "d2", ("b", "c")),
            dim(b, "d3", ("a", "c"), (10.0, 5.0), (0.0, 5.0)),
        ),
        T,
    )
    assert [f.code for f in out.failures] == ["closed_chain"]


def test_d5_chain_wrap_at_180(b: "Builder") -> None:
    dy = 10.0 * math.sin(math.radians(0.0001))
    out = check_d5(
        snap(
            b,
            dim(b, "d1", ("a", "b")),
            dim(b, "d2", ("b", "c")),
            dim(b, "d3", ("a", "c"), (10.0, 0.0), (0.0, dy)),
        ),
        T,
    )
    assert [f.code for f in out.failures] == ["closed_chain"]


def test_d5_horizontal_and_vertical_same_entities_ok(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            dim(b, "d1", ("a", "b")),
            dim(b, "d2", ("a", "b"), (0.0, 0.0), (0.0, 10.0)),
        ),
        T,
    )
    assert out.failures == ()


def test_d5_chain_separate_views_ok(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            dim(b, "d1", ("a", "b")),
            dim(b, "d2", ("b", "c")),
            dim(b, "d3", ("a", "c"), view="v_b"),
        ),
        T,
    )
    assert out.failures == ()


def test_d5_unknown_parenthesized_stays_out_of_graph(b: "Builder") -> None:
    out = check_d5(
        snap(
            b,
            dim(b, "d1", ("a", "b")),
            dim(b, "d2", ("b", "c")),
            dim(b, "d3", ("a", "c"), parenthesized=None),
        ),
        T,
    )
    assert out.failures == ()
    assert out.status == "not_evaluated"
    assert dict(out.parts)["duplicates"] == "not_evaluated"
    assert "dimension_data_missing" in out.reasons


def test_d5_arc_and_ordinate_skipped(b: "Builder") -> None:
    arc = b.annotation(
        "d2",
        dimension_lines=[b.arc((0.0, 0.0), 5.0, 0.0, 90.0)],
        extension_lines=[b.ext("a", (0.0, 0.0), (1.0, 1.0)), b.ext("b", (5.0, 0.0), (6.0, 1.0))],
        parameters=["P2"],
        parenthesized=False,
        view="v_a",
    )
    ordinate = b.annotation(
        "d3",
        dimension_lines=[b.line((0.0, 0.0), (10.0, 0.0))],
        extension_lines=[b.ext("a", (0.0, 0.0), (1.0, 1.0))],
        parameters=["P3"],
        parenthesized=False,
        view="v_a",
    )
    out = check_d5(snap(b, dim(b, "d1", ("a", "b")), arc, ordinate), T)
    assert out.failures == ()


def test_d5_two_cycles_deterministic(b: "Builder") -> None:
    annotations = [
        dim(b, "d1", ("a", "b")),
        dim(b, "d2", ("b", "c")),
        dim(b, "d3", ("a", "c")),
        dim(b, "d4", ("a", "b"), (0.0, 5.0), (10.0, 5.0)),
    ]
    forward = check_d5(snap(b, *annotations), T)
    backward = check_d5(snap(b, *reversed(annotations)), T)
    assert forward.failures == backward.failures
    assert [keys(f.items) for f in forward.failures] == [["d1", "d2", "d3"], ["d1", "d4"]]


def _custom(  # noqa: PLR0913
    b: "Builder",
    key: str,
    extension_lines: Sequence[tuple[str, tuple[float, float]]],
    dimension_lines: Sequence[object],
    *,
    kind: str = "dimension",
    parameters: Sequence[str] | None = None,
) -> Annotation:
    return b.annotation(
        key,
        kind=kind,  # pyright: ignore[reportArgumentType]
        dimension_lines=dimension_lines,  # pyright: ignore[reportArgumentType]
        extension_lines=[b.ext(e, p, p) for e, p in extension_lines],
        parameters=(f"P_{key}@S",) if parameters is None else parameters,
        parenthesized=False,
        view="v_a",
    )


def test_d5_same_entity_twice_not_a_candidate(b: "Builder") -> None:
    twice = ("a", (0.0, 0.0)), ("a", (10.0, 0.0))
    first = _custom(b, "d1", twice, [b.line((0.0, 0.0), (10.0, 0.0))])
    second = _custom(b, "d2", twice, [b.line((0.0, 5.0), (10.0, 5.0))])
    assert check_d5(snap(b, first, second), T).failures == ()


def test_d5_empty_entity_not_a_candidate(b: "Builder") -> None:
    pair = ("", (0.0, 0.0)), ("x", (10.0, 0.0))
    first = _custom(b, "d1", pair, [b.line((0.0, 0.0), (10.0, 0.0))])
    second = _custom(b, "d2", pair, [b.line((0.0, 5.0), (10.0, 5.0))])
    assert check_d5(snap(b, first, second), T).failures == ()


def test_d5_mixed_polyline_and_arc_not_a_candidate(b: "Builder") -> None:
    pair = ("a", (0.0, 0.0)), ("b", (10.0, 0.0))
    mixed = _custom(b, "d1", pair, [b.line((0.0, 0.0), (10.0, 0.0)), b.arc((0.0, 0.0), 5.0, 0, 90)])
    plain = _custom(b, "d2", pair, [b.line((0.0, 5.0), (10.0, 5.0))])
    assert check_d5(snap(b, mixed, plain), T).failures == ()


def test_d5_leading_zero_segment_uses_next_segment(b: "Builder") -> None:
    pair = ("a", (0.0, 0.0)), ("b", (10.0, 0.0))
    vertical = _custom(b, "d1", pair, [b.line((0.0, 0.0), (0.0, 0.0), (0.0, 10.0))])
    horizontal = _custom(b, "d2", pair, [b.line((0.0, 5.0), (10.0, 5.0))])
    assert check_d5(snap(b, vertical, horizontal), T).failures == ()


def test_d5_zero_length_line_not_a_candidate(b: "Builder") -> None:
    pair = ("a", (0.0, 0.0)), ("b", (10.0, 0.0))
    point = _custom(b, "d1", pair, [b.line((0.0, 0.0), (0.0, 0.0), (0.0, 0.0))])
    horizontal = _custom(b, "d2", pair, [b.line((0.0, 5.0), (10.0, 5.0))])
    assert check_d5(snap(b, point, horizontal), T).failures == ()


def test_d5_three_extension_lines_not_a_candidate(b: "Builder") -> None:
    three = ("a", (0.0, 0.0)), ("b", (10.0, 0.0)), ("c", (20.0, 0.0))
    pair = ("a", (0.0, 0.0)), ("b", (10.0, 0.0))
    first = _custom(b, "d1", three, [b.line((0.0, 0.0), (10.0, 0.0))])
    second = _custom(b, "d2", pair, [b.line((0.0, 5.0), (10.0, 5.0))])
    assert check_d5(snap(b, first, second), T).failures == ()


def test_d5_non_dimension_kind_not_a_candidate(b: "Builder") -> None:
    pair = ("a", (0.0, 0.0)), ("b", (10.0, 0.0))
    first = _custom(b, "c1", pair, [b.line((0.0, 0.0), (10.0, 0.0))], kind="callout", parameters=[])
    second = _custom(
        b, "c2", pair, [b.line((0.0, 5.0), (10.0, 5.0))], kind="callout", parameters=[]
    )
    assert check_d5(snap(b, first, second), T).failures == ()
