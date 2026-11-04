"""Bad input to get_execution_status and cancel_execution: every case is a catalogued error."""

import pytest
from cad_application.testing.tool_rig import ToolRig, make_tool_rig
from cad_ir.core.json_types import JsonValue

UNKNOWN_JOB = "job_00000000000000000000000077"
MAX_WAIT_MS = 20_000


@pytest.mark.parametrize("tool", ["get_execution_status", "cancel_execution"])
@pytest.mark.parametrize(
    "execution_id",
    [
        None,
        5,
        True,
        [],
        {},
        "",
        "job_",
        "rep_00000000000000000000000001",
        "snap_00000000000000000000000001",
        "job_0000000000000000000000001",
        "job_000000000000000000000000001",
        "job_0000000000000000000000000I",
        "job_0000000000000000000000000i",
        "job_00000000000000000000000001\n",
        " job_00000000000000000000000001",
        "JOB_00000000000000000000000001",
        "job_" + "\u0660" * 26,
        "job_" + "0" * 10_000,
        "job_00000000000000000000000001\x00",
    ],
)
def test_bad_execution_ids_are_schema_invalid(tool: str, execution_id: JsonValue) -> None:
    rig = make_tool_rig()
    result = rig.call(tool, {"execution_id": execution_id})
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"


@pytest.mark.parametrize(
    "wait_ms",
    [-1, -(10**30), 20_001, 10**30, 1.5, 1.0, "5", "", None, True, False, [], {}, float("inf")],
)
def test_bad_wait_ms_is_schema_invalid(wait_ms: JsonValue) -> None:
    rig = make_tool_rig()
    result = rig.call("get_execution_status", {"execution_id": UNKNOWN_JOB, "wait_ms": wait_ms})
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"


@pytest.mark.parametrize("wait_ms", [0, 1, MAX_WAIT_MS])
def test_good_wait_ms_boundaries(wait_ms: int) -> None:
    rig = make_tool_rig()
    result = rig.call("get_execution_status", {"execution_id": UNKNOWN_JOB, "wait_ms": wait_ms})
    assert ToolRig.code_of(result) == "EXEC_NOT_FOUND"


@pytest.mark.parametrize("keep", ["yes", 1, 0, None, [], {}])
def test_bad_keep_partial_is_schema_invalid(keep: JsonValue) -> None:
    rig = make_tool_rig()
    result = rig.call("cancel_execution", {"execution_id": UNKNOWN_JOB, "keep_partial": keep})
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"


def test_unknown_job_is_exec_not_found_for_status_and_cancel() -> None:
    rig = make_tool_rig()
    for tool in ("get_execution_status", "cancel_execution"):
        result = rig.call(tool, {"execution_id": UNKNOWN_JOB})
        assert ToolRig.code_of(result) == "EXEC_NOT_FOUND"
