"""Tool contract files (spec 12.4.1), read from the schemas embedded by the generator.

``load_contracts`` has no I/O: the contract files are part of ``cad_ir.generated.schemas``. The
annotation derivation is the one function of 12.4.1, tested on every contract file.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, cast
from urllib.parse import urljoin

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.schemas import SCHEMAS

MCP_PREFIX: Final = "https://sw-mcp.invalid/schemas/mcp/"
_COMMON_ID: Final = "https://sw-mcp.invalid/schemas/common/v0.json"
_META_PREFIX: Final = MCP_PREFIX + "contract/"
_DESTRUCTIVE: Final = frozenset({"delete_feature", "close_cad_file"})
_IDEMPOTENT_KINDS: Final = frozenset({"store", "cad-read"})


def _resolve_refs(node: JsonValue, base_uri: str) -> JsonValue:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            full = urljoin(base_uri, ref)
            doc_uri, _, frag = full.partition("#")
            target_doc = SCHEMAS.get(doc_uri)
            if isinstance(target_doc, dict):
                target: JsonValue = target_doc
                if frag:
                    for part in frag.lstrip("/").split("/"):
                        if isinstance(target, dict):
                            target = target.get(part)
                if isinstance(target, dict):
                    merged: dict[str, JsonValue] = dict(target)
                    for key, value in node.items():
                        if key != "$ref":
                            merged[key] = value
                    return _resolve_refs(merged, doc_uri)
        return {key: _resolve_refs(value, base_uri) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, base_uri) for item in node]
    return node


def _envelope_output_schema(
    output_node: Mapping[str, JsonValue],
    schema_id: str,
    errors: tuple[str, ...],
) -> dict[str, JsonValue]:
    resolved_output = cast("dict[str, JsonValue]", _resolve_refs(dict(output_node), schema_id))
    common_doc = SCHEMAS.get(_COMMON_ID)
    assert isinstance(common_doc, dict)
    defs = common_doc.get("$defs")
    assert isinstance(defs, dict)
    envelope_def = defs.get("Envelope")
    assert isinstance(envelope_def, dict)
    env_props = envelope_def.get("properties")
    assert isinstance(env_props, dict)
    ids_schema = _resolve_refs(env_props.get("ids"), _COMMON_ID)
    code_schema: dict[str, JsonValue] = (
        {"type": "string", "enum": list(errors)} if errors else {"type": "string"}
    )
    error_schema: dict[str, JsonValue] = {
        "type": "object",
        "required": ["code", "message", "retryable"],
        "additionalProperties": False,
        "properties": {
            "code": code_schema,
            "message": {"type": "string"},
            "retryable": {"enum": ["never", "after_fix", "safe"]},
            "details": {"type": "object"},
        },
    }
    return {
        "type": "object",
        "required": ["ok", "data", "error", "ids"],
        "additionalProperties": False,
        "properties": {
            "ok": {"type": "boolean"},
            "data": {"anyOf": [resolved_output, {"type": "null"}]},
            "error": {"anyOf": [error_schema, {"type": "null"}]},
            "ids": ids_schema,
        },
        "if": {"properties": {"ok": {"const": True}}},
        "then": {
            "properties": {
                "data": resolved_output,
                "error": {"type": "null"},
            }
        },
        "else": {
            "properties": {
                "data": {"type": "null"},
                "error": error_schema,
            }
        },
    }


def _empty_schema() -> dict[str, JsonValue]:
    return {}


@dataclass(frozen=True, slots=True)
class Example:
    arguments: JsonValue
    response: JsonValue


@dataclass(frozen=True, slots=True)
class ToolContract:
    schema_id: str
    name: str
    description: str
    toolset: str
    phase: str
    kind: str
    mutates: bool
    errors: tuple[str, ...]
    examples: tuple[Example, ...]
    deprecated: bool = False
    replacement: str | None = None
    input_schema: dict[str, JsonValue] = field(default_factory=_empty_schema)
    output_schema: dict[str, JsonValue] = field(default_factory=_empty_schema)

    @property
    def input_ref(self) -> str:
        return f"{self.schema_id}#/input"

    @property
    def output_ref(self) -> str:
        return f"{self.schema_id}#/output"

    def annotations(self) -> Mapping[str, bool]:
        """MCP tool annotations (12.4.1, ADR-044): all four hints are always written."""
        return {
            "readOnlyHint": not self.mutates,
            "destructiveHint": self.name in _DESTRUCTIVE,
            "idempotentHint": self.kind in _IDEMPOTENT_KINDS,
            "openWorldHint": False,
        }

    def tool_definition(self) -> dict[str, JsonValue]:
        """Full MCP tool definition for ``tools/list`` (12.3, 12.4.1)."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "annotations": dict(self.annotations()),
        }

    @staticmethod
    def from_json(doc: Mapping[str, JsonValue]) -> "ToolContract":
        """A contract from its JSON; the file is checked against the meta-schema elsewhere."""
        schema_id = _text(doc, "$id")
        errors = tuple(str(code) for code in _items(doc, "errors"))
        raw_input = doc.get("input")
        raw_output = doc.get("output")
        input_schema: dict[str, JsonValue] = (
            dict(raw_input) if isinstance(raw_input, dict) else {"type": "object"}
        )
        output_node: dict[str, JsonValue] = (
            dict(raw_output) if isinstance(raw_output, dict) else {"type": "object"}
        )
        return ToolContract(
            schema_id=schema_id,
            name=_text(doc, "name"),
            description=_text(doc, "description"),
            toolset=_text(doc, "toolset"),
            phase=_text(doc, "phase"),
            kind=_text(doc, "kind"),
            mutates=doc.get("mutates") is True,
            errors=errors,
            examples=tuple(_example(item) for item in _items(doc, "examples")),
            deprecated=doc.get("deprecated") is True,
            replacement=_optional_text(doc, "replacement"),
            input_schema=input_schema,
            output_schema=_envelope_output_schema(output_node, schema_id, errors),
        )


def _text(doc: Mapping[str, JsonValue], key: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str):
        raise ValueError(f"contract field {key!r} must be a string")
    return value


def _optional_text(doc: Mapping[str, JsonValue], key: str) -> str | None:
    return None if doc.get(key) is None else _text(doc, key)


def _items(doc: Mapping[str, JsonValue], key: str) -> list[JsonValue]:
    value = doc.get(key)
    if not isinstance(value, list):
        raise ValueError(f"contract field {key!r} must be a list")
    return value


def _example(item: JsonValue) -> Example:
    if not isinstance(item, dict):
        raise ValueError("a contract example must be an object")
    return Example(item.get("arguments"), item.get("response"))


def load_contracts() -> Mapping[str, ToolContract]:
    """Every tool contract, by tool name."""
    found: dict[str, ToolContract] = {}
    for schema_id, doc in SCHEMAS.items():
        if schema_id.startswith(MCP_PREFIX) and not schema_id.startswith(_META_PREFIX):
            if not isinstance(doc, dict):
                raise ValueError(f"{schema_id} is not an object")
            contract = ToolContract.from_json(doc)
            found[contract.name] = contract
    return MappingProxyType(dict(sorted(found.items())))
