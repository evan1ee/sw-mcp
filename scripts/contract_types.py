"""Read `schemas/ipc/` into a small type model for the emitters (ADR-051).

The supported shapes are a closed set: objects with ``properties`` and ``required``, arrays,
``string``, ``integer``, ``number``, ``boolean``, ``const``, string ``enum``, ``$ref`` to the same
contract or to ``common``, and ``anyOf`` of one type with ``null``. A ``$ref`` to another contract
and an object without ``properties`` are opaque JSON. Anything else stops with an error naming the
schema path.
"""

import json
import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IPC_DIR = "ipc"
COMMON_FILE = "common/v0.json"
ERRORS_FILE = "common/errors.json"
STRUCTURAL = frozenset(
    {"type", "properties", "required", "items", "enum", "const", "$ref", "anyOf"}
    | {"additionalProperties"}
)
ANNOTATIONS = frozenset(
    {"description", "title", "$comment", "default", "examples", "format", "pattern"}
    | {"minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength", "uniqueItems"}
)
NULLABLE_BRANCHES = 2
PRIMITIVES = {"string", "integer", "number", "boolean"}


@dataclass(frozen=True)
class TypeRef:
    """One field type. ``name`` is set for class/enum, ``item`` for list/nullable."""

    kind: str  # string integer number boolean opaque const enum class list nullable
    name: str = ""
    item: "TypeRef | None" = None
    values: tuple[str, ...] = ()  # enum members
    const: str | bool | None = None


@dataclass(frozen=True)
class Field:
    json_name: str
    type: TypeRef
    required: bool


@dataclass(frozen=True)
class ObjectDef:
    name: str
    fields: tuple[Field, ...]


@dataclass(frozen=True)
class Model:
    protocol_version: str
    objects: tuple[ObjectDef, ...]
    enums: tuple[tuple[str, tuple[str, ...]], ...]
    aliases: tuple[tuple[str, TypeRef], ...]


def pascal(text: str) -> str:
    cleaned = text.replace(".", "_").replace(":", "_").replace("-", "_")
    return "".join(part[:1].upper() + part[1:] for part in cleaned.split("_"))


def _fail(where: str, message: str) -> SystemExit:
    return SystemExit(f"{where}: {message} (ADR-051)")


class _Builder:
    def __init__(self, docs: dict[str, Any]) -> None:
        self.docs = docs
        self.objects: dict[str, ObjectDef] = {}
        self.enums: dict[str, tuple[str, ...]] = {}
        self.aliases: dict[str, TypeRef] = {}
        self._building: set[str] = set()

    def _class_name(self, path: str, def_name: str) -> str:
        op = self.docs[path].get("x-op") if path.startswith(f"{IPC_DIR}/ops/") else None
        return (pascal(op) if isinstance(op, str) else "") + def_name

    def define(self, path: str, def_name: str, *, alias: bool) -> TypeRef:
        """Register a ``$defs`` entry: objects become classes, enums become enums."""
        node = self.docs[path]["$defs"][def_name]
        where = f"schemas/{path}#/$defs/{def_name}"
        name = self._class_name(path, def_name)
        if "properties" in node:
            self._object(path, name, node, where)
            return TypeRef("class", name)
        if "enum" in node:
            result = self._enum(name, node, where)
        else:
            result = self.resolve(path, node, where, name)
        if alias:
            self.aliases[name] = result
        return result

    def _object(self, path: str, name: str, node: dict[str, Any], where: str) -> None:
        if name in self.objects or name in self._building:
            return
        self._building.add(name)
        self._check_keys(node, where)
        properties: dict[str, Any] = node["properties"]
        required = set(node.get("required", []))
        for missing in sorted(required - set(properties)):
            raise _fail(where, f"required field {missing!r} is not in properties")
        fields = tuple(
            Field(
                key,
                self.resolve(
                    path, sub, f"{where}/properties/{key}", name + pascal(key.lstrip("_"))
                ),
                key in required,
            )
            for key, sub in properties.items()
        )
        self.objects[name] = ObjectDef(name, fields)

    def _enum(self, name: str, node: dict[str, Any], where: str) -> TypeRef:
        values = node["enum"]
        if not values or not all(isinstance(v, str) for v in values):
            raise _fail(where, "only string enums are supported")
        self.enums[name] = tuple(values)
        return TypeRef("enum", name, values=tuple(values))

    def _check_keys(self, node: dict[str, Any], where: str) -> None:
        for key in node:
            if key not in STRUCTURAL and key not in ANNOTATIONS and not key.startswith("x-"):
                raise _fail(where, f"unsupported keyword {key!r}")

    def _ref(self, path: str, node: dict[str, Any], where: str) -> TypeRef:
        file_part, _, fragment = str(node["$ref"]).partition("#")
        target = (
            posixpath.normpath(posixpath.join(posixpath.dirname(path), file_part))
            if file_part
            else path
        )
        if target == ERRORS_FILE:
            return TypeRef("string")
        if target != COMMON_FILE and not target.startswith(f"{IPC_DIR}/"):
            return TypeRef("opaque")
        prefix = "/$defs/"
        if (
            not fragment.startswith(prefix)
            or fragment[len(prefix) :] not in self.docs[target]["$defs"]
        ):
            raise _fail(where, f"unresolved $ref {node['$ref']!r}")
        return self.define(target, fragment[len(prefix) :], alias=False)

    def resolve(self, path: str, node: dict[str, Any], where: str, hint: str) -> TypeRef:
        self._check_keys(node, where)
        if "$ref" in node:
            return self._ref(path, node, where)
        if "anyOf" in node:
            return self._nullable(path, node, where, hint)
        if "const" in node:
            return self._const(node, where)
        if "enum" in node:
            return self._enum(hint, node, where)
        return self._plain(path, node, where, hint)

    def _const(self, node: dict[str, Any], where: str) -> TypeRef:
        value = node["const"]
        if not isinstance(value, (str, bool)):
            raise _fail(where, "only string and boolean const are supported")
        return TypeRef("const", const=value)

    def _plain(self, path: str, node: dict[str, Any], where: str, hint: str) -> TypeRef:
        kind = node.get("type")
        if kind in PRIMITIVES:
            return TypeRef(kind)
        if kind == "array":
            if "items" not in node:
                raise _fail(where, "array without items")
            return TypeRef("list", item=self.resolve(path, node["items"], f"{where}/items", hint))
        if (kind == "object" and "properties" not in node) or (
            kind is None and not set(node) & STRUCTURAL
        ):
            return TypeRef("opaque")
        raise _fail(where, f"unsupported shape (type {kind!r}); object types need a $defs entry")

    def _nullable(self, path: str, node: dict[str, Any], where: str, hint: str) -> TypeRef:
        branches: list[dict[str, Any]] = node["anyOf"]
        nulls = [b for b in branches if b == {"type": "null"}]
        if len(branches) != NULLABLE_BRANCHES or len(nulls) != 1:
            raise _fail(where, "anyOf must be one type and null")
        other = next(b for b in branches if b != {"type": "null"})
        return TypeRef("nullable", item=self.resolve(path, other, f"{where}/anyOf", hint))


def _load_docs(root: Path) -> dict[str, Any]:
    base = root / "schemas"
    return {
        p.relative_to(base).as_posix(): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(base.rglob("*.json"), key=lambda p: p.as_posix())
    }


def build_model(root: Path) -> Model:
    docs = _load_docs(root)
    version = docs[f"{IPC_DIR}/v0.json"].get("x-protocol-version")
    if not isinstance(version, str):
        raise _fail("schemas/ipc/v0.json", "missing x-protocol-version")
    builder = _Builder(docs)
    ipc_paths = [p for p in docs if p.startswith(f"{IPC_DIR}/")]
    ipc_paths.sort(key=lambda p: (p != f"{IPC_DIR}/v0.json", p))
    for path in ipc_paths:
        for def_name in docs[path].get("$defs", {}):
            builder.define(path, def_name, alias=True)
    return Model(
        version,
        tuple(builder.objects.values()),
        tuple(builder.enums.items()),
        tuple(builder.aliases.items()),
    )
