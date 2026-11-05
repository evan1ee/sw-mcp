"""Tool contract files (spec 12.4.1), the registry and the handlers' error lists (12.4.2)."""

import random

import pytest
from cad_application.testing.tool_rig import ToolRig, make_tool_rig
from cad_application.tools.context import Call
from cad_application.tools.contracts import ToolContract, load_contracts
from cad_application.tools.registry import ContractViolation, ToolRegistry, UnknownTool
from cad_application.tools.result import Ids, ToolResult, error
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated.error_codes import ErrorCode
from cad_ir.generated.schemas import SCHEMAS

MCP_PREFIX = "https://sw-mcp.invalid/schemas/mcp/"
META_SCHEMA = MCP_PREFIX + "contract/v0.json"
ENVELOPE = "https://sw-mcp.invalid/schemas/common/v0.json#/$defs/Envelope"
PHASE_1A = {"check_drawing", "get_drawing_report", "get_execution_status", "cancel_execution"}
PART_MVP = {
    "apply_part_graph",
    "validate_part_graph",
    "list_feature_types",
    "get_feature_schema",
}
SHIPPED = PHASE_1A | PART_MVP
FIRST_SENTENCE_MAX = 120
SUMMARY_MAX = 200

type Doc = dict[str, JsonValue]


def _contract_docs() -> dict[str, Doc]:
    found: dict[str, Doc] = {}
    for schema_id, doc in SCHEMAS.items():
        if schema_id.startswith(MCP_PREFIX) and not schema_id.startswith(MCP_PREFIX + "contract/"):
            assert isinstance(doc, dict)
            found[schema_id] = doc
    return found


def _first_sentence(text: str) -> str:
    return text.split(". ", maxsplit=1)[0].removesuffix(".")


def test_contract_files_valid_against_meta_schema() -> None:
    docs = _contract_docs()
    assert {str(d["name"]) for d in docs.values()} == SHIPPED
    for schema_id, doc in docs.items():
        assert validate_against_schema(doc, META_SCHEMA) == ()
        assert schema_id == f"{MCP_PREFIX}{doc['name']}.json"


def test_load_contracts_reads_the_four_phase_1a_tools() -> None:
    contracts = load_contracts()
    assert set(contracts) == SHIPPED
    assert all(contracts[n].phase == "1a" for n in PHASE_1A)
    assert all(contracts[n].phase == "1c" for n in PART_MVP)
    assert all(c.input_ref.endswith("#/input") for c in contracts.values())
    assert all(c.output_ref.endswith("#/output") for c in contracts.values())


@pytest.mark.parametrize("name", sorted(SHIPPED))
def test_description_first_sentence_within_120(name: str) -> None:
    contract = load_contracts()[name]
    assert len(_first_sentence(contract.description)) <= FIRST_SENTENCE_MAX
    assert len(contract.description) <= 400  # noqa: PLR2004


@pytest.mark.parametrize("name", sorted(SHIPPED))
def test_input_schemas_forbid_unknown_properties(name: str) -> None:
    doc = next(d for d in _contract_docs().values() if d["name"] == name)
    assert isinstance(doc["input"], dict)
    assert doc["input"]["additionalProperties"] is False


def _synthetic(name: str, kind: str, mutates: bool) -> ToolContract:
    return ToolContract.from_json(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{MCP_PREFIX}{name}.json",
            "name": name,
            "description": "A synthetic contract.",
            "toolset": "detail",
            "phase": "2",
            "kind": kind,
            "mutates": mutates,
            "input": {"type": "object"},
            "output": {"type": "object"},
            "errors": ["IR_SCHEMA_INVALID"],
            "examples": [{"arguments": {}, "response": {}}],
        }
    )


def test_annotations_derivation() -> None:
    contracts = load_contracts()
    expected = {
        "check_drawing": (True, False, False),
        "get_drawing_report": (True, False, True),
        "get_execution_status": (True, False, True),
        "cancel_execution": (False, False, True),
        "apply_part_graph": (False, False, False),
        "validate_part_graph": (True, False, True),
        "list_feature_types": (True, False, True),
        "get_feature_schema": (True, False, True),
    }
    for name, (read_only, destructive, idempotent) in expected.items():
        assert contracts[name].annotations() == {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": idempotent,
            "openWorldHint": False,
        }, name


def test_annotations_for_destructive_tools() -> None:
    delete = _synthetic("delete_feature", "job", mutates=True).annotations()
    assert delete["destructiveHint"] is True
    assert delete["readOnlyHint"] is False
    assert delete["idempotentHint"] is False
    close = _synthetic("close_cad_file", "cad-session", mutates=False).annotations()
    assert close["destructiveHint"] is True
    assert close["readOnlyHint"] is True
    assert _synthetic("read_things", "cad-read", mutates=False).annotations()["idempotentHint"]
    assert not _synthetic("run_things", "cad-session", mutates=True).annotations()["readOnlyHint"]


@pytest.mark.parametrize("name", sorted(SHIPPED))
def test_examples_validate(name: str) -> None:
    contract = load_contracts()[name]
    assert len(contract.examples) >= 2  # noqa: PLR2004
    outcomes: set[bool] = set()
    for example in contract.examples:
        assert validate_against_schema(example.response, ENVELOPE) == ()
        response = example.response
        assert isinstance(response, dict)
        outcomes.add(response["ok"] is True)
        if response["ok"]:
            assert validate_against_schema(example.arguments, contract.input_ref) == ()
            assert validate_against_schema(response["data"], contract.output_ref) == ()
        else:
            error = response["error"]
            assert isinstance(error, dict)
            assert error["code"] in contract.errors
            if error["code"] != "IR_SCHEMA_INVALID":
                assert validate_against_schema(example.arguments, contract.input_ref) == ()
    assert outcomes == {True, False}


def test_unknown_tool_raises() -> None:
    rig = make_tool_rig()
    with pytest.raises(UnknownTool):
        rig.registry.call("delete_feature", {}, "req_00000000000000000000000001")


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("check_drawing", {"path": "C:\\Work\\a.slddrw", "drawing_intent": {}}),
        ("check_drawing", {"path": "C:\\Work\\a.slddrw", "request_id": "req_1"}),
        ("get_drawing_report", {"report_id": "rep_00000000000000000000000001", "extra": 1}),
        ("get_execution_status", {"execution_id": "job_00000000000000000000000001", "x": 1}),
        ("cancel_execution", {"execution_id": "job_00000000000000000000000001", "x": 1}),
    ],
)
def test_unknown_property_is_schema_invalid(tool: str, arguments: Doc) -> None:
    result = make_tool_rig().call(tool, arguments)
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"
    envelope = result.envelope
    assert isinstance(envelope, dict)
    error = envelope["error"]
    assert isinstance(error, dict)
    details = error["details"]
    assert isinstance(details, dict)
    issues = details["issues"]
    assert isinstance(issues, list)
    assert issues
    assert all(isinstance(i, dict) and "pointer" in i for i in issues)


@pytest.mark.parametrize("tool", sorted(PHASE_1A))
@pytest.mark.parametrize("arguments", [None, [], "text", 5, True, [{"path": "x"}]])
def test_arguments_that_are_not_an_object_are_schema_invalid(
    tool: str, arguments: JsonValue
) -> None:
    result = make_tool_rig().call(tool, arguments)
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"


def test_issue_list_is_capped() -> None:
    sheets: list[JsonValue] = [""] * 500
    result = make_tool_rig().call("check_drawing", {"path": "C:\\Work\\a.slddrw", "sheets": sheets})
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"
    details = ToolRig.error_of(result)["details"]
    assert isinstance(details, dict)
    issues = details["issues"]
    assert isinstance(issues, list)
    assert len(issues) <= 20  # noqa: PLR2004


def test_error_results_carry_a_short_summary() -> None:
    result = make_tool_rig().call("check_drawing", {})
    assert 0 < len(result.summary) <= SUMMARY_MAX


# --- the handlers return only listed errors -----------------------------------------------

ID_JOB = "job_00000000000000000000000099"
ID_REP = "rep_00000000000000000000000099"
DRAWING = "C:\\Work\\a.slddrw"

ERROR_PATHS: list[tuple[str, Doc]] = [
    ("check_drawing", {}),
    ("check_drawing", {"path": 5}),
    ("check_drawing", {"path": "D:\\Elsewhere\\a.slddrw"}),
    ("check_drawing", {"path": "relative\\a.slddrw"}),
    ("check_drawing", {"path": "C:\\Work\\missing.slddrw"}),
    ("check_drawing", {"path": "C:\\Work\\notes.txt"}),
    ("check_drawing", {"path": DRAWING, "sheets": []}),
    ("check_drawing", {"path": DRAWING, "sheets": ["A", "A"]}),
    ("get_drawing_report", {}),
    ("get_drawing_report", {"report_id": ID_REP, "execution_id": ID_JOB}),
    ("get_drawing_report", {"report_id": ID_REP}),
    ("get_drawing_report", {"execution_id": ID_JOB}),
    ("get_drawing_report", {"report_id": ID_REP, "cursor": "x"}),
    ("get_drawing_report", {"report_id": ID_REP, "section": "warnings", "cursor": "x"}),
    ("get_execution_status", {}),
    ("get_execution_status", {"execution_id": ID_JOB}),
    ("get_execution_status", {"execution_id": ID_JOB, "wait_ms": 20_001}),
    ("cancel_execution", {}),
    ("cancel_execution", {"execution_id": ID_JOB}),
]


@pytest.mark.parametrize(("tool", "arguments"), ERROR_PATHS)
def test_handlers_return_only_listed_errors(tool: str, arguments: Doc) -> None:
    rig = make_tool_rig()
    rig.write_drawing("C:\\Work\\notes.txt")
    result = rig.call(tool, arguments)
    contract = load_contracts()[tool]
    envelope = result.envelope
    assert isinstance(envelope, dict)
    assert envelope["ok"] is False
    assert ToolRig.code_of(result) in contract.errors
    assert ToolRig.code_of(result) in {c.value for c in ErrorCode}
    assert validate_against_schema(envelope, ENVELOPE) == ()


def test_success_paths_validate_against_output_schemas() -> None:
    rig = make_tool_rig()
    rig.write_drawing(DRAWING)
    queued = rig.call("check_drawing", {"path": DRAWING})
    job_id = ToolRig.data_of(queued)["execution_id"]
    for tool in ("get_execution_status", "get_drawing_report", "cancel_execution"):
        result = rig.call(tool, {"execution_id": job_id})
        contract = load_contracts()[tool]
        data = ToolRig.data_of(result)
        assert validate_against_schema(data, contract.output_ref) == ()


# --- bad input at the boundary: nothing raises, every failure is catalogued ---------------

PROPERTY_NAMES = [
    "path",
    "sheets",
    "report_id",
    "execution_id",
    "detail",
    "section",
    "cursor",
    "page_size",
    "wait_ms",
    "keep_partial",
    "drawing_intent",
]
SCALARS: list[JsonValue] = [
    None,
    True,
    False,
    0,
    -1,
    1,
    200,
    201,
    20_000,
    20_001,
    10**30,
    -(10**30),
    1.5,
    2.0,
    -0.0,
    "",
    " ",
    "summary",
    "full",
    "checks",
    "conflicts",
    "warnings",
    "soft_metrics",
    "C:\\Work\a.slddrw",
    "C:\\Work\notes.txt",
    "\\?\\C:\\Work\a.slddrw",
    "~",
    "%TEMP%",
    "\u202e\u0000\ud800",
    "\u00fc\u00f1\u00ef" * 50,
    ID_JOB,
    ID_REP,
    "x" * 5000,
]


def _random_value(rng: random.Random, depth: int) -> JsonValue:
    pick = rng.random()
    if depth <= 0 or pick < 0.6:  # noqa: PLR2004
        return rng.choice(SCALARS)
    if pick < 0.8:  # noqa: PLR2004
        return [_random_value(rng, depth - 1) for _ in range(rng.randint(0, 4))]
    names = rng.sample(PROPERTY_NAMES, rng.randint(0, 3))
    return {name: _random_value(rng, depth - 1) for name in names}


VALID_BASE: dict[str, Doc] = {
    "check_drawing": {"path": DRAWING},
    "get_drawing_report": {"report_id": ID_REP},
    "get_execution_status": {"execution_id": ID_JOB},
    "cancel_execution": {"execution_id": ID_JOB},
}


def _random_arguments(rng: random.Random, tool: str) -> JsonValue:
    """Arguments that are valid but for one random change, or fully random."""
    mode = rng.random()
    if mode < 0.1:  # noqa: PLR2004
        return _random_value(rng, 2)
    if mode < 0.4:  # noqa: PLR2004
        names = rng.sample(PROPERTY_NAMES, rng.randint(0, 5))
        return {name: _random_value(rng, 2) for name in names}
    arguments = dict(VALID_BASE[tool])
    arguments[rng.choice(PROPERTY_NAMES)] = _random_value(rng, 2)
    return arguments


@pytest.mark.parametrize("tool", sorted(PHASE_1A))
def test_random_arguments_never_raise(tool: str) -> None:
    rng = random.Random(20261104)
    rig = make_tool_rig()
    rig.write_drawing(DRAWING)
    contract = load_contracts()[tool]
    for _ in range(600):
        result = rig.call(tool, _random_arguments(rng, tool))
        code = ToolRig.code_of(result)
        assert code is None or code in contract.errors


@pytest.mark.parametrize("tool", sorted(PHASE_1A))
def test_deeply_nested_arguments_are_schema_invalid(tool: str) -> None:
    nested: JsonValue = "leaf"
    for _ in range(5000):
        nested = [nested]
    wrapped: JsonValue = {"path": nested, "execution_id": nested, "report_id": nested}
    for arguments in (nested, wrapped):
        result = make_tool_rig().call(tool, arguments)
        assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"


def test_registry_raises_on_unlisted_code() -> None:
    def lost(_call: Call) -> ToolResult:
        return error(
            "BACKEND_LOST", "The add-in is gone.", None, Ids("req_00000000000000000000000001")
        )

    handlers = {name: lost for name in load_contracts()}
    registry = ToolRegistry(load_contracts(), handlers, verify=True)
    with pytest.raises(ContractViolation):
        registry.call(
            "check_drawing", {"path": "C:\\Work\a.slddrw"}, "req_00000000000000000000000001"
        )
