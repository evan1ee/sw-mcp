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
SNAPSHOT_ID = "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"
REPORT_ID = "https://sw-mcp.invalid/schemas/drawing-report/v0.json"
TEMPLATE_ID = "https://sw-mcp.invalid/schemas/drawing-template/v0.json"
LAYOUT_ID = "https://sw-mcp.invalid/schemas/drawing-layout/v0.json"
INTENT_ID = "https://sw-mcp.invalid/schemas/drawing-intent/v0.json"
SCHEME_ID = "https://sw-mcp.invalid/schemas/resolved-scheme/v0.json"
PART_GRAPH_ID = "https://sw-mcp.invalid/schemas/part-feature-graph/v0.json"

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


def _snapshot_cases(kind: str) -> list[Json]:
    directory = FIXTURES_DIR / "drawing-geometry-snapshot" / kind
    return [pytest.param(path, id=path.stem) for path in sorted(directory.glob("*.json"))]


@pytest.mark.parametrize("path", _snapshot_cases("valid"))
def test_snapshot_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), SNAPSHOT_ID) == []


@pytest.mark.parametrize("path", _snapshot_cases("invalid"))
def test_snapshot_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), SNAPSHOT_ID) != []


def _report_cases(kind: str) -> list[Json]:
    directory = FIXTURES_DIR / "drawing-report" / kind
    return [pytest.param(path, id=path.stem) for path in sorted(directory.glob("*.json"))]


def test_report_fixtures_exist_for_both_kinds() -> None:
    assert _report_cases("valid")
    assert _report_cases("invalid")


@pytest.mark.parametrize("path", _report_cases("valid"))
def test_report_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), REPORT_ID) == []


@pytest.mark.parametrize("path", _report_cases("invalid"))
def test_report_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), REPORT_ID) != []


def test_snapshot_rejects_nan() -> None:
    instance = _load(FIXTURES_DIR / "drawing-geometry-snapshot" / "valid" / "two_dimensions.json")
    edges = instance["sheets"]["s_0123456789"]["views"]["v_front"]["edges"]
    edges[0]["curve"]["polyline"][0][0] = float("nan")
    issues = _issues(instance, SNAPSHOT_ID)
    assert [i.pointer for i in issues] == [
        "/sheets/s_0123456789/views/v_front/edges/0/curve/polyline/0/0"
    ]


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


IPC_ID = "https://sw-mcp.invalid/schemas/ipc/v0.json"
IPC_DIR = SCHEMAS_DIR / "ipc"
IPC_FIXTURES = FIXTURES_DIR / "ipc"
STRUCTURAL_PREFIX = "structural_"
MUTATES_VALUES = ("document", "session", "none")


def _op_prefix(op: str) -> str:
    return "".join(part.capitalize() for part in op.replace("_", ".").split("."))


def _ipc_defs() -> dict[str, tuple[str, Json]]:
    """Fixture name -> (schema reference, def) for the IPC messages and every operation."""
    defs: dict[str, tuple[str, Json]] = {}
    root = IPC_DIR / "v0.json"
    if root.is_file():
        for name, node in _load(root)["$defs"].items():
            defs[name] = (f"{IPC_ID}#/$defs/{name}", node)
    for path in sorted((IPC_DIR / "ops").glob("*.json")):
        doc = _load(path)
        for name, node in doc["$defs"].items():
            defs[_op_prefix(doc["x-op"]) + name] = (f"{doc['$id']}#/$defs/{name}", node)
    return defs


def _ipc_cases(kind: str) -> list[Json]:
    cases: list[Json] = []
    for path in sorted((IPC_FIXTURES / kind).glob("*.json")):
        name = path.stem.removeprefix(STRUCTURAL_PREFIX)
        for index, instance in enumerate(_load(path)):
            cases.append(pytest.param(name, instance, id=f"{path.stem}[{index}]"))
    return cases


def _ipc_issues(name: str, instance: Json) -> list[Json]:
    return _issues(instance, _ipc_defs()[name][0])


@pytest.mark.parametrize(("name", "instance"), _ipc_cases("valid"))
def test_ipc_valid_accepted(name: str, instance: Json) -> None:
    assert _ipc_issues(name, instance) == []


@pytest.mark.parametrize(("name", "instance"), _ipc_cases("invalid"))
def test_ipc_invalid_rejected(name: str, instance: Json) -> None:
    """Both the schema-only and the ``structural_`` cases are schema violations."""
    assert _ipc_issues(name, instance) != []


def _fixture_names(kind: str) -> set[str]:
    return {p.stem for p in (IPC_FIXTURES / kind).glob("*.json")}


def test_every_ipc_def_has_fixtures() -> None:
    defs = _ipc_defs()
    assert "Request" in defs
    with_required = {name for name, (_, node) in defs.items() if node.get("required")}
    invalid = _fixture_names("invalid")
    plain = {n for n in invalid if not n.startswith(STRUCTURAL_PREFIX)}
    structural = {n.removeprefix(STRUCTURAL_PREFIX) for n in invalid if n not in plain}
    assert _fixture_names("valid") == set(defs)
    assert with_required <= plain
    assert with_required <= structural
    assert plain <= set(defs)
    assert structural <= set(defs)


def _ops_files() -> list[Path]:
    return sorted((IPC_DIR / "ops").glob("*.json"))


def test_ops_files_exist() -> None:
    assert {p.name for p in _ops_files()} >= {"document.open.json", "document.close.json"}


@pytest.mark.parametrize("path", _ops_files(), ids=lambda p: p.name)
def test_ops_schemas_declare_annotations(path: Path) -> None:
    doc = _load(path)
    assert doc["x-op"] == path.stem.removesuffix(".json")
    assert doc["x-mutates"] in MUTATES_VALUES
    assert doc["x-since"] == "0.1"
    errors: list[str] = doc["x-errors"]
    catalogue: set[str] = {
        b["const"] for b in _load(SCHEMAS_DIR / "common" / "errors.json")["oneOf"]
    }
    assert set(errors) <= catalogue
    assert len(set(errors)) == len(errors)
    defs: dict[str, Json] = doc["$defs"]
    assert {"Params", "Result"} <= set(defs)


STORE_ID = "https://sw-mcp.invalid/schemas/store/v0.json"
CONFIG_ID = "https://sw-mcp.invalid/schemas/config/v1.json"
TITLE_BLOCK_ID = "https://sw-mcp.invalid/schemas/config/title-block/v1.json"
CONTRACT_META_ID = "https://sw-mcp.invalid/schemas/mcp/contract/v0.json"
TITLE_BLOCK_PREFIX = "title_block_"


def _store_defs() -> set[str]:
    return set(_load(SCHEMAS_DIR / "store" / "v0.json")["$defs"])


def _store_cases(kind: str) -> list[Json]:
    cases: list[Json] = []
    for path in sorted((FIXTURES_DIR / "store" / kind).glob("*.json")):
        for index, instance in enumerate(_load(path)):
            cases.append(pytest.param(path.stem, instance, id=f"{path.stem}[{index}]"))
    return cases


def test_every_store_def_has_both_kinds_of_fixture() -> None:
    valid = {p.stem for p in (FIXTURES_DIR / "store" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "store" / "invalid").glob("*.json")}
    assert valid == invalid == _store_defs()


@pytest.mark.parametrize(("name", "instance"), _store_cases("valid"))
def test_store_valid_accepted(name: str, instance: Json) -> None:
    assert _issues(instance, f"{STORE_ID}#/$defs/{name}") == []


@pytest.mark.parametrize(("name", "instance"), _store_cases("invalid"))
def test_store_invalid_rejected(name: str, instance: Json) -> None:
    assert _issues(instance, f"{STORE_ID}#/$defs/{name}") != []


def _single_cases(group: str, kind: str, *, title_block: bool = False) -> list[Json]:
    directory = FIXTURES_DIR / group / kind
    paths = [
        p
        for p in sorted(directory.glob("*.json"))
        if p.stem.startswith(TITLE_BLOCK_PREFIX) == title_block
    ]
    return [pytest.param(path, id=path.stem) for path in paths]


@pytest.mark.parametrize("path", _single_cases("config", "valid"))
def test_config_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), CONFIG_ID) == []


@pytest.mark.parametrize("path", _single_cases("config", "invalid"))
def test_config_invalid_rejected(path: Path) -> None:
    """Unknown keys, wrong types and a missing or wrong ``config_version`` are all errors."""
    assert _issues(_load(path), CONFIG_ID) != []


def test_config_invalid_cases_cover_the_named_failures() -> None:
    names = {p.stem for p in (FIXTURES_DIR / "config" / "invalid").glob("*.json")}
    assert {"unknown_top_key", "wrong_type", "missing_config_version"} <= names


@pytest.mark.parametrize("path", _single_cases("config", "valid", title_block=True))
def test_title_block_mapping_schema(path: Path) -> None:
    assert _issues(_load(path), TITLE_BLOCK_ID) == []


@pytest.mark.parametrize("path", _single_cases("config", "invalid", title_block=True))
def test_title_block_mapping_schema_rejects(path: Path) -> None:
    assert _issues(_load(path), TITLE_BLOCK_ID) != []


@pytest.mark.parametrize("path", _single_cases("mcp-contract", "valid"))
def test_contract_meta_schema_valid(path: Path) -> None:
    assert _issues(_load(path), CONTRACT_META_ID) == []


@pytest.mark.parametrize("path", _single_cases("mcp-contract", "invalid"))
def test_contract_meta_schema_invalid(path: Path) -> None:
    assert _issues(_load(path), CONTRACT_META_ID) != []


def test_contract_meta_schema_valid_and_invalid() -> None:
    """The named failures of 12.4.1 each have a fixture."""
    names = {p.stem for p in (FIXTURES_DIR / "mcp-contract" / "invalid").glob("*.json")}
    assert {
        "bad_name",
        "description_too_long",
        "unknown_toolset",
        "unknown_error_code",
        "empty_examples",
        "non_boolean_deprecated",
    } <= names
    assert {p.stem for p in (FIXTURES_DIR / "mcp-contract" / "valid").glob("*.json")}


def test_store_ids_are_one_def_per_prefix() -> None:
    defs = _load(SCHEMAS_DIR / "store" / "v0.json")["$defs"]
    for name, prefix in (
        ("JobId", "job"),
        ("ReportId", "rep"),
        ("SnapshotId", "snap"),
        ("DrawingId", "drw"),
        ("RequestId", "req"),
    ):
        assert defs[name]["pattern"] == f"^{prefix}_[0-9A-HJKMNP-TV-Z]{{26}}$"


def _template_cases(kind: str) -> list[Json]:
    return [
        pytest.param(path, id=path.stem)
        for path in sorted((FIXTURES_DIR / "drawing-template" / kind).glob("*.json"))
    ]


def test_template_fixtures_exist_for_both_kinds() -> None:
    valid = {p.stem for p in (FIXTURES_DIR / "drawing-template" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "drawing-template" / "invalid").glob("*.json")}
    assert {"full", "minimal"} <= valid
    assert {
        "wrong_module",
        "units_inches",
        "unknown_key",
        "bad_paper_size",
        "margin_zero",
        "no_zones",
        "zone_three_coords",
        "bad_item_key",
        "source_empty",
        "source_unknown_kind",
        "height_zero",
    } <= invalid


@pytest.mark.parametrize("path", _template_cases("valid"))
def test_template_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), TEMPLATE_ID) == []


@pytest.mark.parametrize("path", _template_cases("invalid"))
def test_template_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), TEMPLATE_ID) != []


def _layout_cases(kind: str) -> list[Json]:
    return [
        pytest.param(path, id=path.stem)
        for path in sorted((FIXTURES_DIR / "drawing-layout" / kind).glob("*.json"))
    ]


def test_layout_fixtures_exist_for_both_kinds() -> None:
    valid = {p.stem for p in (FIXTURES_DIR / "drawing-layout" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "drawing-layout" / "invalid").glob("*.json")}
    assert {"minimal", "three_view_a3"} <= valid
    assert {"wrong_module", "missing_sheet", "bad_scale"} <= invalid


@pytest.mark.parametrize("path", _layout_cases("valid"))
def test_layout_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), LAYOUT_ID) == []


@pytest.mark.parametrize("path", _layout_cases("invalid"))
def test_layout_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), LAYOUT_ID) != []


def _intent_cases(kind: str) -> list[Json]:
    return [
        pytest.param(path, id=path.stem)
        for path in sorted((FIXTURES_DIR / "drawing-intent" / kind).glob("*.json"))
    ]


def test_intent_fixtures_exist_for_both_kinds() -> None:
    valid = {p.stem for p in (FIXTURES_DIR / "drawing-intent" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "drawing-intent" / "invalid").glob("*.json")}
    assert {"minimal"} <= valid
    assert {"wrong_module", "missing_id"} <= invalid


@pytest.mark.parametrize("path", _intent_cases("valid"))
def test_intent_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), INTENT_ID) == []


@pytest.mark.parametrize("path", _intent_cases("invalid"))
def test_intent_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), INTENT_ID) != []


def _scheme_cases(kind: str) -> list[Json]:
    return [
        pytest.param(path, id=path.stem)
        for path in sorted((FIXTURES_DIR / "resolved-scheme" / kind).glob("*.json"))
    ]


def test_scheme_fixtures_exist_for_both_kinds() -> None:
    valid = {p.stem for p in (FIXTURES_DIR / "resolved-scheme" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "resolved-scheme" / "invalid").glob("*.json")}
    assert {"minimal"} <= valid
    assert {"missing_entries", "bad_status"} <= invalid


@pytest.mark.parametrize("path", _scheme_cases("valid"))
def test_scheme_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), SCHEME_ID) == []


@pytest.mark.parametrize("path", _scheme_cases("invalid"))
def test_scheme_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), SCHEME_ID) != []


def _part_cases(kind: str) -> list[Json]:
    return [
        pytest.param(path, id=path.stem)
        for path in sorted((FIXTURES_DIR / "part-feature-graph" / kind).glob("*.json"))
    ]


def test_part_fixtures_exist_for_both_kinds() -> None:
    valid = {p.stem for p in (FIXTURES_DIR / "part-feature-graph" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "part-feature-graph" / "invalid").glob("*.json")}
    assert {"plate_4h"} <= valid
    assert {
        "unknown_field",
        "blind_needs_depth",
        "through_all_has_depth",
        "wrong_module",
        "wrong_units",
    } <= invalid


@pytest.mark.parametrize("path", _part_cases("valid"))
def test_part_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), PART_GRAPH_ID) == []


@pytest.mark.parametrize("path", _part_cases("invalid"))
def test_part_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), PART_GRAPH_ID) != []


EVIDENCE_ID = "https://sw-mcp.invalid/schemas/execution-evidence/v0.json"


def _evidence_cases(kind: str) -> list[Json]:
    return [
        pytest.param(path, id=path.stem)
        for path in sorted((FIXTURES_DIR / "execution-evidence" / kind).glob("*.json"))
    ]


def test_evidence_fixtures_cover_the_named_rules() -> None:
    """Each rule of 8.9.6 and ADR-064 has a fixture that breaks it."""
    valid = {p.stem for p in (FIXTURES_DIR / "execution-evidence" / "valid").glob("*.json")}
    invalid = {p.stem for p in (FIXTURES_DIR / "execution-evidence" / "invalid").glob("*.json")}
    assert {"committed_plate", "failed_feature_contract", "recovered_after_crash"} <= valid
    assert {
        "wrong_schema_version",
        "unknown_top_level_key",
        "committed_with_failure_class",
        "committed_not_verified",
        "committed_not_published",
        "not_evaluated_without_reason",
        "not_evaluated_with_unknown_reason",
        "not_applicable_without_reason",
        "passed_with_reason",
        "blocked_by_on_a_sent_operation",
        "contract_unknown_level",
        "contract_check_without_required",
    } <= invalid


@pytest.mark.parametrize("path", _evidence_cases("valid"))
def test_evidence_valid_accepted(path: Path) -> None:
    assert _issues(_load(path), EVIDENCE_ID) == []


@pytest.mark.parametrize("path", _evidence_cases("invalid"))
def test_evidence_invalid_rejected(path: Path) -> None:
    assert _issues(_load(path), EVIDENCE_ID) != []
