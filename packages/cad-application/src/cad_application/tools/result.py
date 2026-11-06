"""Handler results: the ADR-037 envelope and the one-line summary of ADR-044 (spec 12.4.2)."""

from dataclasses import dataclass
from typing import Final, Protocol

from cad_ir.core.json_types import JsonValue

from cad_application.jobs.model import error_object

SUMMARY_MAX: Final = 200
_ELLIPSIS: Final = "…"


@dataclass(frozen=True, slots=True)
class Ids:
    """The ``ids`` block: ``request_id`` always; the others when the call names a job or report."""

    request_id: str
    execution_id: str | None = None
    report_id: str | None = None

    def to_json(self) -> dict[str, JsonValue]:
        found: dict[str, JsonValue] = {"request_id": self.request_id}
        if self.execution_id is not None:
            found["execution_id"] = self.execution_id
        if self.report_id is not None:
            found["report_id"] = self.report_id
        return found


@dataclass(frozen=True, slots=True)
class ToolResult:
    """What a handler returns: the envelope (``structuredContent``) and the summary (text)."""

    envelope: JsonValue
    summary: str


def clip(text: str) -> str:
    """One line of at most ``SUMMARY_MAX`` characters."""
    line = " ".join(text.split())
    return line if len(line) <= SUMMARY_MAX else line[: SUMMARY_MAX - 1] + _ELLIPSIS


def ok(data: JsonValue, ids: Ids, summary: str) -> ToolResult:
    envelope: JsonValue = {"ok": True, "data": data, "error": None, "ids": ids.to_json()}
    return ToolResult(envelope, clip(summary))


def error(
    code: str, message: str, details: JsonValue, ids: Ids, summary: str | None = None
) -> ToolResult:
    """An error envelope; ``retryable`` comes from the catalogue default (ADR-037)."""
    body = error_object(code, message, details if isinstance(details, dict) else None)
    envelope: JsonValue = {"ok": False, "data": None, "error": body, "ids": ids.to_json()}
    return ToolResult(envelope, clip(summary if summary is not None else f"{code}: {message}"))


class Failure(Protocol):
    """Anything that carries a catalogue code: ``ToolError`` and ``StoreError``."""

    @property
    def code(self) -> str: ...

    @property
    def message(self) -> str: ...

    @property
    def details(self) -> JsonValue: ...


def failure(problem: Failure, ids: Ids) -> ToolResult:
    return error(problem.code, problem.message, problem.details, ids)
