"""``get_execution_status`` (spec 12.4.5, ADR-043): state, progress, outcome and a long-poll."""

from typing import Final

from cad_ir.core.json_types import JsonValue

from cad_application.jobs.model import JobView, UnknownJobError
from cad_application.ports import Clock
from cad_application.store.codec import Obj, parse_ts
from cad_application.store.job_records import JobRecord
from cad_application.tools.context import Call, ToolContext
from cad_application.tools.result import ToolResult, error, ok
from cad_application.tools.summaries import status_line

POLL_HINT_MS: Final = 1000
_PROGRESS_STATES: Final = frozenset({"EXECUTING", "VERIFYING"})
_ERROR_STATES: Final = frozenset({"FAILED", "ABORTED"})
_MS_PER_S: Final = 1000


def not_found(call: Call, execution_id: str) -> ToolResult:
    return error(
        "EXEC_NOT_FOUND",
        "No job with this ID is known; it may have expired.",
        None,
        call.ids(execution_id=execution_id),
        f"EXEC_NOT_FOUND: {execution_id}",
    )


def _elapsed_ms(record: JobRecord, clock: Clock) -> int | None:
    """Milliseconds since ``started_at``, until the job ended (or until now)."""
    if record.started_at is None:
        return None
    try:
        started = parse_ts(record.started_at)
        ended = parse_ts(record.ended_at) if record.ended_at is not None else clock.now()
    except ValueError:
        return None
    return max(0, int((ended - started).total_seconds() * _MS_PER_S))


def status_data(view: JobView, *, changed: bool, clock: Clock) -> Obj:
    """The ``data`` of 12.4.5: which fields appear depends on the state."""
    record = view.record
    warnings: list[JsonValue] = [w.to_json() for w in record.warnings]
    data: Obj = {
        "execution_id": record.job_id,
        "job_type": record.job_type,
        "state": record.state,
        "started_at": record.started_at,
        "warnings": warnings,
        "documents_unknown": [d.path for d in record.documents if d.state == "unknown"],
    }
    if record.state == "PLANNED":
        data["queued_position"] = view.queued_position or 0
    if record.state in _PROGRESS_STATES and record.progress is not None:
        data["progress"] = record.progress.to_json()
    elapsed = _elapsed_ms(record, clock)
    if elapsed is not None:
        data["elapsed_ms"] = elapsed
    if not record.is_final:
        data["retry_after_ms"] = 0 if changed else POLL_HINT_MS
    if record.state == "COMMITTED" and record.report_id is not None:
        data["report_id"] = record.report_id
    if record.state in _ERROR_STATES and record.error is not None:
        data["error"] = record.error
    return data


def handle(ctx: ToolContext, call: Call) -> ToolResult:
    execution_id = call.arguments["execution_id"]
    wait_ms = call.arguments.get("wait_ms", 0)
    assert isinstance(execution_id, str)
    assert isinstance(wait_ms, int)
    try:
        view, changed = ctx.engine.wait_for_change(execution_id, wait_ms)
    except UnknownJobError:
        return not_found(call, execution_id)
    data = status_data(view, changed=changed, clock=ctx.clock)
    summary = status_line(view.record, view.queued_position)
    return ok(data, call.ids(execution_id=execution_id), summary)
