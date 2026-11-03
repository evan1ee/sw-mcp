"""Validation issues and the capped, deterministic issue report (spec 3.4.7)."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from cad_ir.core.json_types import JsonValue
from cad_ir.generated import ErrorCode

type Severity = Literal["error", "warning"]

MAX_REPORTED_ISSUES: Final = 50


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One validation finding. ``pointer`` is an RFC 6901 pointer into the submitted document."""

    code: ErrorCode
    pointer: str
    message: str
    severity: Severity = "error"
    expected: tuple[str, ...] | None = None
    ref: str | None = None
    patch_op: int | None = None

    def to_json(self) -> dict[str, JsonValue]:
        """The wire form (``common/v0.json#/$defs/ValidationIssue``): defaults are omitted."""
        out: dict[str, JsonValue] = {
            "code": self.code.value,
            "pointer": self.pointer,
            "message": self.message,
        }
        if self.severity != "error":
            out["severity"] = self.severity
        if self.expected is not None:
            out["expected"] = list(self.expected)
        if self.ref is not None:
            out["ref"] = self.ref
        if self.patch_op is not None:
            out["patch_op"] = self.patch_op
        return out


@dataclass(frozen=True, slots=True)
class IssueReport:
    """The first ``MAX_REPORTED_ISSUES`` issues in order, and how many were left out.

    ``omitted_errors`` counts the left-out issues whose severity is ``error``.
    """

    issues: tuple[ValidationIssue, ...]
    omitted: int
    omitted_errors: int

    def __post_init__(self) -> None:
        if not 0 <= self.omitted_errors <= self.omitted:
            raise ValueError(
                f"omitted_errors must be between 0 and omitted ({self.omitted}),"
                f" got {self.omitted_errors}"
            )

    @property
    def has_errors(self) -> bool:
        return self.omitted_errors > 0 or any(i.severity == "error" for i in self.issues)


_INDEX: Final = re.compile(r"0|[1-9][0-9]*")

type _TokenKey = tuple[int, int, str]
type SortKey = tuple[tuple[_TokenKey, ...], str, str]


def _token_key(token: str) -> _TokenKey:
    """Indices compare as numbers and sort before other tokens, which compare by code point."""
    return (0, int(token), "") if _INDEX.fullmatch(token) else (1, 0, token)


def pointer_sort_key(pointer: str) -> tuple[_TokenKey, ...]:
    """Total order on RFC 6901 pointers, token by token (spec 3.4.7)."""
    if not pointer:
        return ()
    tokens = (t.replace("~1", "/").replace("~0", "~") for t in pointer.split("/")[1:])
    return tuple(_token_key(t) for t in tokens)


def issue_sort_key(issue: ValidationIssue) -> SortKey:
    """Deterministic order: by pointer, then code, then message (spec 3.4.7)."""
    return (pointer_sort_key(issue.pointer), issue.code.value, issue.message)


def build_report(issues: Iterable[ValidationIssue]) -> IssueReport:
    """Sort the issues, keep the first 50 and count the rest."""
    ordered = sorted(issues, key=issue_sort_key)
    kept = tuple(ordered[:MAX_REPORTED_ISSUES])
    rest = ordered[MAX_REPORTED_ISSUES:]
    return IssueReport(
        issues=kept,
        omitted=len(rest),
        omitted_errors=sum(1 for i in rest if i.severity == "error"),
    )
