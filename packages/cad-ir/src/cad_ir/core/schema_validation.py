"""JSON Schema validation producing deterministic validation issues (spec 3.4.7, 3.4.8).

Pure: the schema registry is built once at import from the embedded ``SCHEMAS`` constant.
"""

import copy
import json
import math
import re
from collections.abc import Iterator, Mapping
from typing import Any, Final

from jsonschema import Draft202012Validator, ValidationError, validators
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from cad_ir.core.issues import ValidationIssue, issue_sort_key
from cad_ir.core.json_types import JsonValue
from cad_ir.core.pointer import json_pointer
from cad_ir.generated import ErrorCode
from cad_ir.generated.schemas import SCHEMAS

_MESSAGE_MAX: Final = 200


def _whole_string_pattern(
    validator: Any, pattern: str, instance: Any, schema: Mapping[str, Any]
) -> Iterator[ValidationError]:
    """``pattern`` with whole-string semantics (spec 3.4.8).

    Python's ``$`` also matches before a final newline, so ``^...$`` through ``re.search`` would
    accept ``"bore_1\\n"``. Strip the anchors and ``fullmatch`` instead.
    """
    del schema
    if not validator.is_type(instance, "string"):
        return
    core = pattern.removeprefix("^").removesuffix("$")
    if re.fullmatch(core, instance) is None:
        yield ValidationError(f"{instance!r} does not match {pattern!r}")


# jsonschema ships no usable stubs for `extend`.
_extend: Any = validators.extend  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def _is_integer(checker: Any, instance: object) -> bool:
    """``integer`` means a Python ``int`` that is not a ``bool``: ``2.0`` is rejected (3.4.8)."""
    del checker
    return isinstance(instance, int) and not isinstance(instance, bool)


_TYPE_CHECKER: Final[Any] = Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_integer)  # pyright: ignore[reportUnknownMemberType]
_VALIDATOR_CLASS: Final[Any] = _extend(
    Draft202012Validator, {"pattern": _whole_string_pattern}, type_checker=_TYPE_CHECKER
)
_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"


def _build_registry() -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for schema_id, doc in SCHEMAS.items():
        assert isinstance(doc, dict)
        # Without `$schema` on a resource root, jsonschema keeps `_VALIDATOR_CLASS` when a `$ref`
        # crosses into that document; with it, it would switch back to the stock class.
        own = copy.deepcopy(doc)
        assert own.pop("$schema", None) == _DIALECT, schema_id
        contents = own
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)  # pyright: ignore[reportUnknownMemberType]
        registry = registry.with_resource(schema_id, resource)
    return registry


_REGISTRY: Final = _build_registry()


def _non_finite_pointers(value: JsonValue, path: tuple[str | int, ...] = ()) -> Iterator[str]:
    if isinstance(value, float) and not math.isfinite(value):
        yield json_pointer(*path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _non_finite_pointers(item, (*path, index))
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _non_finite_pointers(item, (*path, key))


def _render(value: object) -> str:
    """A JSON value as JSON text (``true``, ``null``), a string as itself."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _expected(error: ValidationError) -> tuple[str, ...] | None:
    value: Any = error.validator_value  # pyright: ignore[reportUnknownMemberType]
    if error.validator == "enum":
        members: list[Any] = value
        return tuple(_render(v) for v in members)
    if error.validator == "const":
        return (_render(value),)
    if error.validator == "type":
        return (value,) if isinstance(value, str) else tuple(_render(v) for v in value)
    return None


def _message(error: ValidationError) -> str:
    """The error message, with JSON values shown as JSON rather than as Python reprs."""
    instance = json.dumps(error.instance, ensure_ascii=False)  # pyright: ignore[reportUnknownMemberType]
    expected = _expected(error)
    if error.validator == "type" and expected is not None:
        return f"{instance} is not of type {', '.join(expected)}"
    if error.validator == "const" and expected is not None:
        return f"{instance} was expected to be {expected[0]}"
    if error.validator == "enum" and expected is not None:
        return f"{instance} is not one of {', '.join(expected)}"
    return error.message


def _one_line(message: str) -> str:
    line = message.splitlines()[0] if message else "schema validation failed"
    return line if len(line) <= _MESSAGE_MAX else line[: _MESSAGE_MAX - 1] + "…"


def _to_issue(error: ValidationError) -> ValidationIssue:
    return ValidationIssue(
        code=ErrorCode.IR_SCHEMA_INVALID,
        pointer=json_pointer(*error.absolute_path),
        message=_one_line(_message(error)),
        expected=_expected(error),
    )


def validate_against_schema(instance: JsonValue, schema_id: str) -> tuple[ValidationIssue, ...]:
    """Validate ``instance`` against a registered schema; every problem is one issue.

    ``schema_id`` is a schema ``$id``, optionally followed by a ``#/$defs/...`` fragment.
    Raises ``KeyError`` when the schema (or the fragment) does not exist. Issues are returned
    in the deterministic order of ``build_report`` (pointer, code, message), without the cap.
    """
    base = schema_id.partition("#")[0]
    if base not in SCHEMAS:
        raise KeyError(schema_id)

    issues = [
        ValidationIssue(
            code=ErrorCode.IR_SCHEMA_INVALID,
            pointer=pointer,
            message="number is not finite (NaN and infinities are not allowed)",
            expected=("finite number",),
        )
        for pointer in _non_finite_pointers(instance)
    ]
    validator: Any = _VALIDATOR_CLASS(
        {"$ref": schema_id},
        registry=_REGISTRY,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    try:
        issues.extend(_to_issue(error) for error in validator.iter_errors(instance))
    except Unresolvable as exc:
        raise KeyError(schema_id) from exc
    return tuple(sorted(issues, key=issue_sort_key))
