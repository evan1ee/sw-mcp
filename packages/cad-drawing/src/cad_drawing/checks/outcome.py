"""Outcomes of the rule checks D5, D8 and D10 (spec 11.5.3).

A check is never ``pass`` when part of it did not run: a found failure gives ``fail``, otherwise
anything unread gives ``not_evaluated`` with reason codes.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from cad_ir.core import JsonValue

type CheckStatus = Literal["pass", "fail", "not_evaluated"]
type ReasonCode = Literal[
    "drawing_intent_required",
    "dimension_data_missing",
    "title_block_mapping_missing",
    "title_block_data_missing",
    "rebuild_data_missing",
    "reopen_not_checked",
]
type RuleCheckId = Literal["D5", "D8", "D10"]

type ItemKey = tuple[str, str, str]
type RuleSortKey = tuple[int, int, tuple[ItemKey, ...], str, tuple[tuple[str, str], ...]]


@dataclass(frozen=True, slots=True)
class RuleItem:
    kind: Literal["annotation", "title_field"]
    id: str
    sheet: str | None

    def sort_key(self) -> ItemKey:
        return (self.kind, self.id, self.sheet or "")

    def to_json(self) -> dict[str, JsonValue]:
        return {"kind": self.kind, "id": self.id, "sheet": self.sheet}


@dataclass(frozen=True, slots=True)
class RuleFailure:
    check: RuleCheckId
    sheet: str | None
    code: str
    items: tuple[RuleItem, ...]
    detail: tuple[tuple[str, str], ...]
    message: str

    def sort_key(self, sheet_index: Mapping[str, int]) -> RuleSortKey:
        """Document-level failures (no sheet) sort before the sheets."""
        index = -1 if self.sheet is None else sheet_index[self.sheet]
        return (
            index,
            int(self.check[1:]),
            tuple(i.sort_key() for i in self.items),
            self.code,
            self.detail,
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "check": self.check,
            "sheet": self.sheet,
            "code": self.code,
            "items": [i.to_json() for i in self.items],
            "detail": {k: v for k, v in self.detail},
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class CheckWarning:
    code: str
    sheet: str
    annotation: str
    message: str

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "code": self.code,
            "sheet": self.sheet,
            "annotation": self.annotation,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    status: CheckStatus
    failures: tuple[RuleFailure, ...] = ()
    reasons: tuple[ReasonCode, ...] = ()
    warnings: tuple[CheckWarning, ...] = ()
    parts: tuple[tuple[str, CheckStatus], ...] = ()


def combine_status(statuses: Iterable[CheckStatus]) -> CheckStatus:
    """``fail`` beats ``not_evaluated`` beats ``pass``; no statuses at all is ``pass``."""
    seen = set(statuses)
    if "fail" in seen:
        return "fail"
    if "not_evaluated" in seen:
        return "not_evaluated"
    return "pass"
