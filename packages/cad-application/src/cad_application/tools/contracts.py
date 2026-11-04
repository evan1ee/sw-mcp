"""Tool contract files (spec 12.4.1), read from the schemas embedded by the generator.

``load_contracts`` has no I/O: the contract files are part of ``cad_ir.generated.schemas``. The
annotation derivation is the one function of 12.4.1, tested on every contract file.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.schemas import SCHEMAS

MCP_PREFIX: Final = "https://sw-mcp.invalid/schemas/mcp/"
_META_PREFIX: Final = MCP_PREFIX + "contract/"
_DESTRUCTIVE: Final = frozenset({"delete_feature", "close_cad_file"})
_IDEMPOTENT_KINDS: Final = frozenset({"store", "cad-read"})


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

    @staticmethod
    def from_json(doc: Mapping[str, JsonValue]) -> "ToolContract":
        """A contract from its JSON; the file is checked against the meta-schema elsewhere."""
        return ToolContract(
            schema_id=_text(doc, "$id"),
            name=_text(doc, "name"),
            description=_text(doc, "description"),
            toolset=_text(doc, "toolset"),
            phase=_text(doc, "phase"),
            kind=_text(doc, "kind"),
            mutates=doc.get("mutates") is True,
            errors=tuple(str(code) for code in _items(doc, "errors")),
            examples=tuple(_example(item) for item in _items(doc, "examples")),
            deprecated=doc.get("deprecated") is True,
            replacement=_optional_text(doc, "replacement"),
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
