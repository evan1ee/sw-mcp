"""``get_authoring_guide``: the guide an agent reads before it writes a Part Feature Graph."""

from cad_ir.core.json_types import JsonValue

from cad_application.authoring_guide import build_guide
from cad_application.tools.context import Call, ToolContext
from cad_application.tools.result import ToolResult, ok


def handle(_ctx: ToolContext, call: Call) -> ToolResult:
    data: JsonValue = {"guide": build_guide()}
    return ok(data, call.ids(), "Part Feature Graph authoring guide")
