"""``get_feature_schema`` (spec 12.3, 12.4.5, design 10): compact schema and example per type."""

from typing import Final

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.schemas import SCHEMAS

from cad_application.tools.context import Call, ToolContext
from cad_application.tools.result import ToolResult, error, ok

_FEATURE_PREFIX: Final = "https://sw-mcp.invalid/schemas/part-feature-graph/features/"
_SUPPORTED_TYPES: Final[tuple[str, ...]] = ("sketch", "extrude", "cut_extrude")


def _feature_entry(feature_type: str) -> dict[str, JsonValue]:
    schema_id = f"{_FEATURE_PREFIX}{feature_type}.json"
    raw = SCHEMAS.get(schema_id)
    assert isinstance(raw, dict)
    compact_schema: dict[str, JsonValue] = {
        k: v for k, v in raw.items() if k not in ("$schema", "$id", "examples")
    }
    examples = raw.get("examples")
    first_ex = examples[0] if isinstance(examples, list) and examples else None
    example: JsonValue = first_ex if isinstance(first_ex, dict) else {}
    return {
        "schema": compact_schema,
        "example": example,
    }


def handle(_ctx: ToolContext, call: Call) -> ToolResult:
    raw_types = call.arguments["types"]
    assert isinstance(raw_types, list)
    requested = [t for t in raw_types if isinstance(t, str)]
    unknown = [t for t in requested if t not in _SUPPORTED_TYPES]
    if unknown:
        first = unknown[0]
        details: dict[str, JsonValue] = {
            "unknown_types": [t for t in unknown],
            "supported_types": list(_SUPPORTED_TYPES),
        }
        return error(
            "IR_SCHEMA_INVALID",
            f"Unknown feature type: {first!r}.",
            details,
            call.ids(),
            f"IR_SCHEMA_INVALID: unknown feature type {first!r}",
        )

    schemas: dict[str, JsonValue] = {t: _feature_entry(t) for t in requested}
    data: JsonValue = {"schemas": schemas}
    return ok(data, call.ids(), f"feature schema for: {', '.join(requested)}")
