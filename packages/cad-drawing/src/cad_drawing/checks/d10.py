"""D10: the drawing rebuilds clean and survives save/reopen (spec 11.5.3)."""

from cad_drawing.checks.outcome import (
    CheckOutcome,
    CheckStatus,
    CheckWarning,
    ReasonCode,
    RuleFailure,
    RuleItem,
)
from cad_drawing.checks.snapshot import Rebuild, RebuildError, Snapshot


def _document_failure(code: str, message: str) -> RuleFailure:
    return RuleFailure(check="D10", sheet=None, code=code, items=(), detail=(), message=message)


def _error_failure(error: RebuildError) -> RuleFailure:
    items = (
        (RuleItem("annotation", error.annotation, error.sheet),)
        if error.annotation is not None
        else ()
    )
    return RuleFailure(
        check="D10",
        sheet=error.sheet,
        code=error.kind,
        items=items,
        detail=(),
        message=error.message,
    )


def _failures(rebuild: Rebuild) -> list[RuleFailure]:
    failures: list[RuleFailure] = []
    if not rebuild.completed:
        failures.append(_document_failure("rebuild_not_completed", "the rebuild did not complete"))
    failures.extend(_error_failure(e) for e in rebuild.errors)
    if rebuild.reopen == "failed":
        failures.append(_document_failure("reopen_failed", "the saved drawing failed to reopen"))
    return failures


def check_d10(snapshot: Snapshot) -> CheckOutcome:
    rebuild = snapshot.rebuild
    if rebuild is None:
        return CheckOutcome("not_evaluated", reasons=("rebuild_data_missing",))
    index = {s.key: s.index for s in snapshot.sheets}
    failures = tuple(sorted(_failures(rebuild), key=lambda f: f.sort_key(index)))
    reasons: tuple[ReasonCode, ...] = (
        ("reopen_not_checked",) if rebuild.reopen == "not_checked" else ()
    )
    status: CheckStatus = "pass"
    if failures:
        status = "fail"
    elif reasons:
        status = "not_evaluated"
    warnings = tuple(
        CheckWarning(
            "silhouette_attachment",
            r.sheet,
            r.annotation,
            "dimension attached to a silhouette edge may dangle after model changes",
        )
        for r in sorted(rebuild.silhouette_attachments, key=lambda r: (r.sheet, r.annotation))
    )
    return CheckOutcome(status, failures=failures, reasons=reasons, warnings=warnings)
