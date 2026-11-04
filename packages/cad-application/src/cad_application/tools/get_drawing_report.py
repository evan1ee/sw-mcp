"""``get_drawing_report`` (spec 12.4.5): a stored report as a summary, in full, or by section."""

from typing import Final, cast

from cad_ir.core.json_types import JsonValue

from cad_application.paths import ToolError
from cad_application.ports import Store
from cad_application.store.codec import Obj
from cad_application.store.errors import StoreError, corrupt
from cad_application.store.job_records import JobRecord
from cad_application.store.records import ReportMeta
from cad_application.tools.context import Call, ToolContext
from cad_application.tools.cursor import clock_ms, decode_cursor, encode_cursor
from cad_application.tools.get_execution_status import not_found
from cad_application.tools.report_views import (
    CorruptReport,
    Section,
    SummaryParts,
    checks_of,
    section_items,
    summary_data,
    verdict_of,
)
from cad_application.tools.result import Ids, ToolResult, error, failure, ok
from cad_application.tools.summaries import no_report_line, report_line, section_line

DEFAULT_PAGE: Final = 50
_PAGED: Final = frozenset({"conflicts", "warnings"})


def _report_not_found(call: Call, report_id: str) -> ToolResult:
    return error(
        "EXEC_NOT_FOUND",
        "No report with this ID is known; it may have expired.",
        None,
        call.ids(report_id=report_id),
        f"EXEC_NOT_FOUND: {report_id}",
    )


def _no_report(call: Call, record: JobRecord) -> ToolResult:
    data: JsonValue = {"execution_id": record.job_id, "state": record.state, "report_id": None}
    summary = no_report_line(record.job_id, record.state)
    return ok(data, call.ids(execution_id=record.job_id), summary)


def _corrupt(report_id: str, reason: str) -> StoreError:
    return corrupt(reason, f"reports\\{report_id}.json")


def _page(
    call: Call, ctx: ToolContext, items: list[JsonValue]
) -> tuple[list[JsonValue], str | None] | ToolError:
    """One page of ``items`` and the cursor of the next one (12.4.2)."""
    size = call.arguments.get("page_size", DEFAULT_PAGE)
    assert isinstance(size, int)
    now = clock_ms(ctx.clock)
    cursor = call.arguments.get("cursor")
    offset = 0
    if isinstance(cursor, str):
        decoded = decode_cursor(cursor, call.arguments, now)
        if isinstance(decoded, ToolError):
            return decoded
        offset = decoded
    page = items[offset : offset + size]
    if offset + size >= len(items):
        return page, None
    return page, encode_cursor(offset + size, now, call.arguments)


def _section_result(
    ctx: ToolContext, call: Call, report: JsonValue, meta: ReportMeta, section: Section
) -> ToolResult:
    items = section_items(report, section)
    ids = call.ids(execution_id=meta.execution_id, report_id=meta.report_id)
    data: Obj = {"report_id": meta.report_id, "section": section}
    if isinstance(items, list) and section in _PAGED:
        paged = _page(call, ctx, items)
        if isinstance(paged, ToolError):
            return failure(paged, ids)
        shown, next_cursor = paged
        data["items"] = shown
        if next_cursor is not None:
            data["next_cursor"] = next_cursor
        summary = section_line(meta.report_id, section, len(shown), len(items))
    else:
        data["items"] = items
        summary = section_line(meta.report_id, section, len(items), len(items))
    return ok(data, ids, summary)


def _summary_result(
    call: Call, report: JsonValue, meta: ReportMeta, store: Store, *, full: bool
) -> ToolResult:
    drawing = store.get_drawing(meta.drawing_id)
    if isinstance(drawing, StoreError):
        return failure(drawing, call.ids())
    if drawing is None:
        return failure(_corrupt(meta.report_id, "drawing_record_missing"), call.ids())
    parts = SummaryParts(
        meta.report_id,
        meta.execution_id,
        drawing.path,
        meta.drawing_id,
        meta.snapshot_id,
        meta.job_warnings,
    )
    data = summary_data(report, parts, full=full)
    ids = call.ids(execution_id=meta.execution_id, report_id=meta.report_id)
    checks = cast("dict[str, dict[str, object]]", checks_of(report))
    return ok(data, ids, report_line(meta.report_id, verdict_of(report), checks))


def _render(ctx: ToolContext, call: Call, store: Store, report_id: str) -> ToolResult:
    stored = store.get_report(report_id)
    if stored is None:
        return _report_not_found(call, report_id)
    if isinstance(stored, StoreError):
        return failure(stored, call.ids(report_id=report_id))
    report, meta = stored
    section = call.arguments.get("section")
    try:
        if isinstance(section, str):
            return _section_result(ctx, call, report, meta, cast("Section", section))
        full = call.arguments.get("detail") == "full"
        return _summary_result(call, report, meta, store, full=full)
    except CorruptReport:
        return failure(_corrupt(report_id, "report_shape"), Ids(call.request_id, None, report_id))


def _by_execution(ctx: ToolContext, call: Call, execution_id: str) -> ToolResult:
    view = ctx.engine.status(execution_id)
    if view is None:
        return not_found(call, execution_id)
    record = view.record
    if record.state != "COMMITTED" or record.report_id is None:
        return _no_report(call, record)
    store = ctx.stores.store_of_report(record.report_id)
    if store is None:
        return _report_not_found(call, record.report_id)
    return _render(ctx, call, store, record.report_id)


def handle(ctx: ToolContext, call: Call) -> ToolResult:
    report_id = call.arguments.get("report_id")
    if isinstance(report_id, str):
        store = ctx.stores.store_of_report(report_id)
        if store is None:
            return _report_not_found(call, report_id)
        return _render(ctx, call, store, report_id)
    execution_id = call.arguments["execution_id"]
    assert isinstance(execution_id, str)
    return _by_execution(ctx, call, execution_id)
