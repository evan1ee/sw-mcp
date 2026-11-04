"""``cancel_execution`` (spec 12.4.5, ADR-053): abort a queued job, ask a running one to stop."""

from cad_ir.core.json_types import JsonValue

from cad_application.jobs.model import UnknownJobError
from cad_application.tools.context import Call, ToolContext
from cad_application.tools.get_execution_status import not_found
from cad_application.tools.result import ToolResult, ok
from cad_application.tools.summaries import cancel_line


def handle(ctx: ToolContext, call: Call) -> ToolResult:
    """``keep_partial`` has no effect: ``check_drawing`` changes nothing (``changes`` is ``[]``)."""
    execution_id = call.arguments["execution_id"]
    assert isinstance(execution_id, str)
    try:
        view = ctx.engine.cancel(execution_id)
    except UnknownJobError:
        return not_found(call, execution_id)
    final = view.record.is_final
    data: JsonValue = {
        "execution_id": execution_id,
        "state": view.state,
        "final": final,
        "changes": [],
    }
    return ok(
        data,
        call.ids(execution_id=execution_id),
        cancel_line(execution_id, view.state, final=final),
    )
