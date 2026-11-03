"""Schema contract tests: every schema is valid 2020-12 and every fixture behaves as labelled."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cad_ir.core.ids import DATUM_LABEL_PATTERN, DOCUMENT_ID_PATTERN, ITEM_ID_PATTERN
from cad_ir.core.schema_validation import validate_against_schema
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "schemas"
COMMON_ID = "https://sw-mcp.invalid/schemas/common/v0.json"
BUNDLE_ID = "https://sw-mcp.invalid/schemas/bundle/v1.json"

type Json = Any


def _load(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_files() -> list[Path]:
    return sorted(SCHEMAS_DIR.rglob("*.json"))


def _issues(instance: Json, schema_id: str) -> list[Json]:
    return list(validate_against_schema(instance, schema_id))


def _common_cases(kind: str) -> list[Json]:
    cases: list[Json] = []
    for path in sorted((FIXTURES_DIR / "common" / kind).glob("*.json")):
        for index, instance in enumerate(_load(path)):
            cases.append(pytest.param(path.stem, instance, id=f"{path.stem}[{index}]"))
    return cases


def _bundle_cases(kind: str) -> list[Json]:
    return [
        pytest.param(path, id=path.stem)
        for path in sorted((FIXTURES_DIR / "bundle" / kind).glob("*.json"))
    ]


def test_schema_files_exist() -> None:
    ids = {_load(p)["$id"] for p in _schema_files()}
    assert {COMMON_ID, BUNDLE_ID, "https://sw-mcp.invalid/schemas/common/errors.json"} <= ids


@pytest.mark.parametrize(
    "path", _schema_files(), ids=lambda p: p.relative_to(SCHEMAS_DIR).as_posix()
)
def test_every_schema_is_valid_2020_12(path: Path) -> None:
    doc = _load(path)
    Draft202012Validator.check_schema(doc)
    assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    relative = path.relative_to(SCHEMAS_DIR).as_posix()
    assert doc["$id"] == f"https://sw-mcp.invalid/schemas/{relative}"


def test_id_patterns_match_python() -> None:
    defs = _load(SCHEMAS_DIR / "common" / "v0.json")["$defs"]
    for name, constant in (
        ("DocumentId", DOCUMENT_ID_PATTERN),
        ("ItemId", ITEM_ID_PATTERN),
        ("DatumLabel", DATUM_LABEL_PATTERN),
    ):
        assert defs[name]["pattern"] == "^" + constant + "$"


def test_every_fixture_def_exists_with_both_kinds() -> None:
    defs = set(_load(SCHEMAS_DIR / "common" / "v0.json")["$defs"])
    valid = {p.stem for p in (FIXTURES_DIR / "common" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "common" / "invalid").glob("*.json")}
    assert valid == invalid == defs


@pytest.mark.parametrize(("name", "instance"), _common_cases("valid"))
def test_common_valid_accepted(name: str, instance: Json) -> None:
    assert _issues(instance, f"{COMMON_ID}#/$defs/{name}") == []


@pytest.mark.parametrize(("name", "instance"), _common_cases("invalid"))
def test_common_invalid_rejected(name: str, instance: Json) -> None:
    assert _issues(instance, f"{COMMON_ID}#/$defs/{name}") != []


@pytest.mark.parametrize("path", _bundle_cases("valid"))
def test_bundle_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), BUNDLE_ID) == []


@pytest.mark.parametrize("path", _bundle_cases("invalid"))
def test_bundle_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), BUNDLE_ID) != []


def _walk(node: Json, path: str = "") -> Iterator[tuple[str, str, Json]]:
    """Yield ``(path, key, value)`` for every key of every object in a schema."""
    if isinstance(node, dict):
        members: dict[str, Json] = node  # pyright: ignore[reportUnknownVariableType]
        for key, value in members.items():
            yield path, key, value
            yield from _walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        items: list[Json] = node  # pyright: ignore[reportUnknownVariableType]
        for index, item in enumerate(items):
            yield from _walk(item, f"{path}/{index}")


def _top_level_alternation(pattern: str) -> bool:
    """True when a ``|`` sits outside every group and character class."""
    depth, in_class, i = 0, False, 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\":
            i += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "|" and depth == 0:
            return True
        i += 1
    return False


def _ends_with_unescaped_dollar(pattern: str) -> bool:
    if not pattern.endswith("$"):
        return False
    backslashes = len(pattern) - 1 - len(pattern[:-1].rstrip("\\"))
    return backslashes % 2 == 0


def test_alternation_checker_detects_bare_alternation() -> None:
    assert _top_level_alternation("^a|b$")
    assert not _top_level_alternation("^(?:a|b)$")
    assert not _top_level_alternation("^[a|b]$")
    assert not _top_level_alternation(r"^a\|b$")
    assert not _ends_with_unescaped_dollar(r"^a\$")
    assert _ends_with_unescaped_dollar("^a$")


@pytest.mark.parametrize(
    "path", _schema_files(), ids=lambda p: p.relative_to(SCHEMAS_DIR).as_posix()
)
def test_patterns_are_anchored_and_portable(path: Path) -> None:
    doc = _load(path)
    for where, key, value in _walk(doc):
        assert key != "patternProperties", f"{where}: use propertyNames (spec 3.4.8)"
        if key == "pattern" and isinstance(value, str):
            assert value.startswith("^"), f"{where}: {value}"
            assert _ends_with_unescaped_dollar(value), f"{where}: {value}"
            assert not _top_level_alternation(value), f"{where}: {value}"


def test_trailing_newline_is_rejected_by_the_project_validator() -> None:
    """The stock validator accepts ``abc\n`` for ``^[a-z]+$``; the project validator must not."""
    schema: dict[str, Any] = {"type": "string", "pattern": "^[a-z]+$"}
    stock: Any = Draft202012Validator(schema)
    assert stock.is_valid("abc\n")
    assert _issues("bore_1\n", f"{COMMON_ID}#/$defs/ItemId") != []
