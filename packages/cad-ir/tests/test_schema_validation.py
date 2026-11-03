import copy
import math

import pytest
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated import ErrorCode

BUNDLE = "https://sw-mcp.invalid/schemas/bundle/v1.json"
COMMON = "https://sw-mcp.invalid/schemas/common/v0.json"


def _example() -> dict[str, JsonValue]:
    return {
        "bundle_schema_version": "1.0",
        "modules": ["part:bracket@4", "design_intent:BRK-001-DES@2", "drawing_intent:BRK-001-DI@3"],
    }


def test_validate_bundle_example_ok() -> None:
    assert validate_against_schema(_example(), BUNDLE) == ()


def test_validate_rejects_nan_with_pointer() -> None:
    doc: JsonValue = {"bundle_schema_version": "1.0", "modules": [math.nan]}
    issues = validate_against_schema(doc, BUNDLE)
    finite = [i for i in issues if i.expected == ("finite number",)]
    assert [(i.pointer, i.code) for i in finite] == [("/modules/0", ErrorCode.IR_SCHEMA_INVALID)]
    assert all(i.code == ErrorCode.IR_SCHEMA_INVALID for i in issues)


@pytest.mark.parametrize("bad", [math.inf, -math.inf])
def test_validate_rejects_infinity_in_nested_value(bad: float) -> None:
    doc: JsonValue = {"a": [1, {"b/c": bad}]}
    issues = validate_against_schema(doc, f"{COMMON}#/$defs/Envelope")
    assert "/a/1/b~1c" in [i.pointer for i in issues if i.expected == ("finite number",)]


def test_validate_does_not_flag_finite_numbers_or_bools() -> None:
    assert validate_against_schema(1.5, f"{COMMON}#/$defs/Length") == ()
    issues = validate_against_schema(True, f"{COMMON}#/$defs/Length")
    assert issues  # a bool is not a number
    assert all(i.expected != ("finite number",) for i in issues)


def test_validate_reports_all_errors_sorted() -> None:
    doc: JsonValue = {**_example(), "extra": 1, "modules": ["foo:x"]}
    issues = validate_against_schema(doc, BUNDLE)
    assert [i.pointer for i in issues] == ["", "/modules/0"]
    assert all(i.code == ErrorCode.IR_SCHEMA_INVALID for i in issues)
    assert all("\n" not in i.message and i.message for i in issues)
    assert issues == validate_against_schema(copy.deepcopy(doc), BUNDLE)


def test_validate_follows_cross_document_refs_with_whole_string_patterns() -> None:
    doc: JsonValue = {"bundle_schema_version": "1.0", "modules": ["part:a\n"]}
    assert [i.pointer for i in validate_against_schema(doc, BUNDLE)] == ["/modules/0"]


def test_validate_does_not_mutate_input() -> None:
    doc = _example()
    before = copy.deepcopy(doc)
    validate_against_schema(doc, BUNDLE)
    assert doc == before


def test_validate_error_carries_expected_values_for_enums() -> None:
    issues = validate_against_schema("cm", f"{COMMON}#/$defs/Units")
    assert len(issues) == 1
    assert issues[0].expected == ("mm", "in")


def test_validate_unknown_schema_id_raises_key_error() -> None:
    with pytest.raises(KeyError):
        validate_against_schema({}, "https://sw-mcp.invalid/schemas/nope/v1.json")
    with pytest.raises(KeyError):
        validate_against_schema({}, f"{COMMON}#/$defs/NoSuchDef")


@pytest.mark.parametrize("value", [2.0, 1.5, "2", None, True, 9007199254740992, 0, -1])
def test_integer_means_a_non_bool_int(value: JsonValue) -> None:
    issues = validate_against_schema(value, f"{COMMON}#/$defs/Revision")
    assert issues != ()


def test_integer_accepts_the_largest_safe_integer() -> None:
    assert validate_against_schema(9007199254740991, f"{COMMON}#/$defs/Revision") == ()
    assert validate_against_schema(2, f"{COMMON}#/$defs/Count") == ()


def test_messages_and_expected_render_json_values() -> None:
    envelope: JsonValue = {"ok": True, "data": None, "error": None, "ids": {"request_id": "r"}}
    assert validate_against_schema(envelope, f"{COMMON}#/$defs/Envelope") == ()
    (issue,) = validate_against_schema(None, f"{COMMON}#/$defs/ItemId")
    assert issue.message == "null is not of type string"
    assert issue.expected == ("string",)
    (flag,) = validate_against_schema(True, f"{COMMON}#/$defs/Units")
    assert flag.message.startswith("true is not one of")
    assert "True" not in flag.message
