"""``list_feature_types`` (spec 12.3, 12.4.5, design 10): supported feature node types."""

from typing import Final

from cad_compiler.registry import get_feature_info
from cad_ir.core.json_types import JsonValue

from cad_application.tools.context import Call, ToolContext
from cad_application.tools.result import ToolResult, ok

MVP_TYPES: Final[tuple[tuple[str, str], ...]] = (
    ("sketch", "2D sketch on a standard plane with line and circle entities."),
    ("extrude", "Blind boss extrude from a closed sketch profile."),
    ("cut_extrude", "Blind or through-all-both cut extrude from a sketch profile."),
    ("linear_pattern", "Linear pattern of seed cut features along 1 or 2 directions."),
    ("circular_pattern", "Circular pattern of seed cut features around an axis."),
)


def handle(_ctx: ToolContext, call: Call) -> ToolResult:
    entries: list[JsonValue] = []
    for name, description in MVP_TYPES:
        info = get_feature_info(name)
        modes = sorted(info.modes) if info is not None else ["create", "read"]
        support: list[JsonValue] = [m for m in modes if m in ("create", "read")]
        entries.append(
            {
                "type": name,
                "description": description,
                "support": support,
            }
        )
    data: JsonValue = {"types": entries}
    names = ", ".join(name for name, _ in MVP_TYPES)
    return ok(data, call.ids(), f"{len(entries)} feature types: {names}")
