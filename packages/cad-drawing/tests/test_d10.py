"""D10: rebuild clean (spec 11.5.3)."""

from typing import TYPE_CHECKING

from cad_drawing.checks.d10 import check_d10
from cad_drawing.checks.snapshot import (
    AnnotationRef,
    Rebuild,
    RebuildError,
    ReopenState,
    Snapshot,
)

if TYPE_CHECKING:
    from conftest import Builder


def snap(
    b: "Builder",
    *,
    completed: bool = True,
    errors: tuple[RebuildError, ...] = (),
    silhouette: tuple[AnnotationRef, ...] = (),
    reopen: ReopenState = "verified",
) -> Snapshot:
    sheets = [
        b.sheet([b.annotation("a1"), b.annotation("a2")], key="s_0", index=0),
        b.sheet([b.annotation("a3")], key="s_1", index=1),
    ]
    return b.snapshot(sheets, Rebuild(completed, errors, silhouette, reopen))


def test_d10_missing_section_not_evaluated(b: "Builder") -> None:
    out = check_d10(b.snapshot([b.sheet()]))
    assert (out.status, out.reasons, out.failures) == (
        "not_evaluated",
        ("rebuild_data_missing",),
        (),
    )


def test_d10_clean_passes(b: "Builder") -> None:
    out = check_d10(snap(b))
    assert (out.status, out.failures, out.reasons, out.warnings) == ("pass", (), (), ())


def test_d10_error_kinds(b: "Builder") -> None:
    errors = (
        RebuildError("rebuild_error", None, None, "model failed"),
        RebuildError("annotation_error", "s_1", "a3", "bad note"),
        RebuildError("dangling", "s_0", "a1", "lost edge"),
    )
    out = check_d10(snap(b, errors=errors))
    assert out.status == "fail"
    assert [(f.code, f.sheet, f.message) for f in out.failures] == [
        ("rebuild_error", None, "model failed"),
        ("dangling", "s_0", "lost edge"),
        ("annotation_error", "s_1", "bad note"),
    ]
    assert out.failures[0].items == ()
    assert [(i.kind, i.id, i.sheet) for i in out.failures[1].items] == [("annotation", "a1", "s_0")]
    assert all(f.check == "D10" and f.detail == () for f in out.failures)


def test_d10_not_completed_fails(b: "Builder") -> None:
    out = check_d10(snap(b, completed=False))
    assert out.status == "fail"
    (failure,) = out.failures
    assert (failure.code, failure.sheet, failure.items) == ("rebuild_not_completed", None, ())


def test_d10_reopen_failed_fails(b: "Builder") -> None:
    out = check_d10(snap(b, reopen="failed"))
    (failure,) = out.failures
    assert (failure.code, failure.sheet, failure.items) == ("reopen_failed", None, ())
    assert out.status == "fail"


def test_d10_not_checked_not_evaluated(b: "Builder") -> None:
    out = check_d10(snap(b, reopen="not_checked"))
    assert (out.status, out.reasons, out.failures) == ("not_evaluated", ("reopen_not_checked",), ())


def test_d10_not_checked_with_error_is_fail(b: "Builder") -> None:
    errors = (RebuildError("dangling", "s_0", "a1", "lost"),)
    out = check_d10(snap(b, errors=errors, reopen="not_checked"))
    assert out.status == "fail"
    assert out.reasons == ("reopen_not_checked",)


def test_d10_silhouette_is_warning_only(b: "Builder") -> None:
    refs = (AnnotationRef("s_1", "a3"), AnnotationRef("s_0", "a2"), AnnotationRef("s_0", "a1"))
    out = check_d10(snap(b, silhouette=refs))
    assert out.status == "pass"
    assert out.failures == ()
    assert [(w.code, w.sheet, w.annotation) for w in out.warnings] == [
        ("silhouette_attachment", "s_0", "a1"),
        ("silhouette_attachment", "s_0", "a2"),
        ("silhouette_attachment", "s_1", "a3"),
    ]
