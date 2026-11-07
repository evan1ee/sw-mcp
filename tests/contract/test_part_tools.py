"""Contract and handler tests for the part graph MCP tools (spec 12.4.5, design 10, Task 10)."""

import json
from typing import Any, cast

import pytest
from cad_application.config.settings import Settings
from cad_application.testing.builders import PROJECT_ROOT
from cad_application.testing.tool_rig import ToolRig, make_tool_rig
from cad_application.tools.context import ToolContext
from cad_application.tools.registry import build_registry
from cad_application.tools.result import SUMMARY_MAX
from cad_ir.core.json_types import JsonValue

from tests.integration.test_plan_job import PLATE_FIXTURE, PartRig

TARGET = "C:\\Work\\plate.SLDPRT"
MAX_WIN_PATH = 260
EXPECTED_MVP_TYPES = 8


def _plate_graph() -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], json.loads(PLATE_FIXTURE.read_text(encoding="utf-8")))


def _ready() -> ToolRig:
    rig = make_tool_rig()
    rig.rig.fs.make_dirs(PROJECT_ROOT)
    return rig


def test_apply_plate_queues() -> None:
    rig = _ready()
    res = rig.call("apply_part_graph", {"graph": _plate_graph(), "target_path": TARGET})
    assert ToolRig.code_of(res) is None
    data = ToolRig.data_of(res)
    assert data == {
        "execution_id": "job_00000000000000000000000001",
        "queued_position": 0,
        "document": "part:plate_4h@1",
    }
    ids = ToolRig.ids_of(res)
    assert ids["execution_id"] == "job_00000000000000000000000001"


def test_apply_bad_graph_no_job() -> None:
    rig = _ready()
    bad = _plate_graph()
    nodes = dict(cast(dict[str, Any], bad["nodes"]))
    sketch = dict(cast(dict[str, Any], nodes["sketch_base"]))
    entities = dict(cast(dict[str, Any], sketch["entities"]))
    # Break the loop so semantic validation fails with IR_RULE_VIOLATED
    entities["l4"] = {"type": "line", "start": [-50, 30], "end": [-50, 0]}
    sketch["entities"] = entities
    nodes["sketch_base"] = sketch
    bad["nodes"] = nodes

    res = rig.call("apply_part_graph", {"graph": bad, "target_path": TARGET})
    assert ToolRig.code_of(res) == "IR_RULE_VIOLATED"
    err = ToolRig.error_of(res)
    details = err.get("details")
    assert isinstance(details, dict)
    issues = details.get("issues")
    assert isinstance(issues, list)
    assert len(issues) > 0
    assert rig.rig.store().list_job_ids() == ()


def test_apply_existing_target_denied() -> None:
    rig = _ready()
    rig.rig.fs.write_atomic(TARGET, b"existing")
    res = rig.call("apply_part_graph", {"graph": _plate_graph(), "target_path": TARGET})
    assert ToolRig.code_of(res) == "AUTH_SOURCE_WRITE_NOT_ALLOWED"
    err = ToolRig.error_of(res)
    assert err.get("details") == {"reason": "file_exists"}
    assert rig.rig.store().list_job_ids() == ()


def test_apply_missing_parent() -> None:
    rig = _ready()
    res = rig.call(
        "apply_part_graph",
        {"graph": _plate_graph(), "target_path": "C:\\Work\\missing_folder\\plate.SLDPRT"},
    )
    assert ToolRig.code_of(res) == "FILE_NOT_FOUND"
    err = ToolRig.error_of(res)
    assert err.get("details") == {"reason": "missing_parent"}
    assert rig.rig.store().list_job_ids() == ()


def test_apply_outside_roots() -> None:
    rig = _ready()
    res = rig.call(
        "apply_part_graph",
        {"graph": _plate_graph(), "target_path": "D:\\Outside\\plate.SLDPRT"},
    )
    assert ToolRig.code_of(res) == "AUTH_PATH_DENIED"
    err = ToolRig.error_of(res)
    assert err.get("details") == {"reason": "outside_roots"}
    assert rig.rig.store().list_job_ids() == ()


def test_apply_wrong_suffix() -> None:
    rig = _ready()
    res = rig.call(
        "apply_part_graph",
        {"graph": _plate_graph(), "target_path": "C:\\Work\\plate.SLDDRW"},
    )
    assert ToolRig.code_of(res) == "IR_SCHEMA_INVALID"
    err = ToolRig.error_of(res)
    assert err.get("details") == {"reason": "suffix"}
    assert rig.rig.store().list_job_ids() == ()


def test_apply_in_vault_denied() -> None:
    rig = make_tool_rig()
    vault_root = "C:\\Vault"
    rig.rig.fs.make_dirs(vault_root)
    settings = Settings(
        allowed_roots=(PROJECT_ROOT, vault_root),
        pdm_vault_roots=(vault_root,),
        local_app_data="C:\\Users\\me\\AppData\\Local",
    )
    ctx = ToolContext(
        engine=rig.rig.engine,
        stores=rig.rig.stores,
        fs=rig.rig.fs,
        clock=rig.rig.clock,
        settings_user=settings,
        project_settings=lambda _root: settings,
        log=rig.rig.log,
    )
    vault_rig = ToolRig(rig.rig, ctx, build_registry(ctx))
    res = vault_rig.call(
        "apply_part_graph",
        {"graph": _plate_graph(), "target_path": "C:\\Vault\\plate.SLDPRT"},
    )
    assert ToolRig.code_of(res) == "AUTH_SOURCE_WRITE_NOT_ALLOWED"
    err = ToolRig.error_of(res)
    assert err.get("details") == {"reason": "in_vault"}


def test_apply_long_path_denied() -> None:
    rig = _ready()
    # working_path adds ".job_<26 chars>.building" (40 chars) before ".SLDPRT".
    # Choose a filename so target_path is < 260 chars, but working_path is >= 260 chars.
    long_name = "a" * 210 + ".SLDPRT"
    long_target = f"C:\\Work\\{long_name}"
    assert len(long_target) < MAX_WIN_PATH
    res = rig.call(
        "apply_part_graph",
        {"graph": _plate_graph(), "target_path": long_target},
    )
    assert ToolRig.code_of(res) == "AUTH_PATH_DENIED"
    err = ToolRig.error_of(res)
    details = err.get("details")
    assert isinstance(details, dict)
    assert details.get("reason") == "path_too_long"
    assert rig.rig.store().list_job_ids() == ()


def test_same_graph_same_revision() -> None:
    rig = _ready()
    first = rig.call(
        "apply_part_graph", {"graph": _plate_graph(), "target_path": "C:\\Work\\p1.SLDPRT"}
    )
    assert ToolRig.data_of(first)["document"] == "part:plate_4h@1"

    second = rig.call(
        "apply_part_graph", {"graph": _plate_graph(), "target_path": "C:\\Work\\p2.SLDPRT"}
    )
    assert ToolRig.data_of(second)["document"] == "part:plate_4h@1"


def test_changed_graph_without_revision_conflicts() -> None:
    rig = _ready()
    rig.call("apply_part_graph", {"graph": _plate_graph(), "target_path": "C:\\Work\\p1.SLDPRT"})

    changed = _plate_graph()
    nodes = dict(cast(dict[str, Any], changed["nodes"]))
    extrude = dict(cast(dict[str, Any], nodes["extrude_base"]))
    extrude["end_condition"] = {"type": "blind", "depth": 20}
    nodes["extrude_base"] = extrude
    changed["nodes"] = nodes

    conflict = rig.call(
        "apply_part_graph", {"graph": changed, "target_path": "C:\\Work\\p2.SLDPRT"}
    )
    assert ToolRig.code_of(conflict) == "REV_CONFLICT"


def test_changed_graph_with_revision_next() -> None:
    rig = _ready()
    rig.call("apply_part_graph", {"graph": _plate_graph(), "target_path": "C:\\Work\\p1.SLDPRT"})

    changed = _plate_graph()
    nodes = dict(cast(dict[str, Any], changed["nodes"]))
    extrude = dict(cast(dict[str, Any], nodes["extrude_base"]))
    extrude["end_condition"] = {"type": "blind", "depth": 20}
    nodes["extrude_base"] = extrude
    changed["nodes"] = nodes

    res = rig.call(
        "apply_part_graph",
        {"graph": changed, "target_path": "C:\\Work\\p2.SLDPRT", "expected_revision": 1},
    )
    assert ToolRig.code_of(res) is None
    assert ToolRig.data_of(res)["document"] == "part:plate_4h@2"


def test_validate_returns_expected() -> None:
    rig = _ready()
    res = rig.call("validate_part_graph", {"graph": _plate_graph()})
    assert ToolRig.code_of(res) is None
    data = ToolRig.data_of(res)
    assert data["valid"] is True
    assert data["issues"] == []
    assert data["build_order"] == ["sketch_base", "extrude_base", "sketch_holes", "cut_holes"]
    expected = data["expected"]
    assert isinstance(expected, dict)
    assert expected["volume_mm3"] == pytest.approx(57989.38, abs=0.01)
    assert expected["solid_body_count"] == 1


def test_list_types() -> None:
    rig = _ready()
    res = rig.call("list_feature_types", {})
    assert ToolRig.code_of(res) is None
    data = ToolRig.data_of(res)
    types = data["types"]
    assert isinstance(types, list)
    assert len(types) == EXPECTED_MVP_TYPES
    names = [t["type"] for t in types if isinstance(t, dict)]
    assert names == [
        "sketch",
        "extrude",
        "cut_extrude",
        "linear_pattern",
        "circular_pattern",
        "mirror",
        "revolve",
        "cut_revolve",
    ]


def test_schema_unknown_type() -> None:
    rig = _ready()
    res = rig.call("get_feature_schema", {"types": ["fillet"]})
    assert ToolRig.code_of(res) == "IR_SCHEMA_INVALID"

    ok_res = rig.call("get_feature_schema", {"types": ["sketch", "extrude"]})
    assert ToolRig.code_of(ok_res) is None
    schemas = ToolRig.data_of(ok_res)["schemas"]
    assert isinstance(schemas, dict)
    assert set(schemas) == {"sketch", "extrude"}


def test_status_has_part_result() -> None:
    part_rig = PartRig()
    ctx = ToolContext(
        engine=part_rig.engine,
        stores=part_rig.stores,
        fs=part_rig.fs,
        clock=part_rig.clock,
        settings_user=part_rig.user_settings,
        project_settings=lambda _root: part_rig.user_settings,
        log=part_rig.log,
    )
    tool_rig = ToolRig(
        rig=cast(Any, part_rig),
        ctx=ctx,
        registry=build_registry(ctx),
    )
    applied = tool_rig.call(
        "apply_part_graph",
        {"graph": _plate_graph(), "target_path": TARGET},
    )
    job_id = str(ToolRig.data_of(applied)["execution_id"])
    assert part_rig.engine.run_next()

    status_res = tool_rig.call("get_execution_status", {"execution_id": job_id})
    assert ToolRig.code_of(status_res) is None
    status_data = ToolRig.data_of(status_res)
    assert status_data["state"] == "COMMITTED"
    assert "part_result" in status_data
    pr = status_data["part_result"]
    assert isinstance(pr, dict)
    assert pr["path"] == TARGET
    assert isinstance(pr["fingerprint"], str)
    assert isinstance(pr["checks"], list)
    assert isinstance(pr["measured"], dict)


def test_summaries_fit() -> None:
    rig = _ready()
    r_apply = rig.call("apply_part_graph", {"graph": _plate_graph(), "target_path": TARGET})
    job_id = str(ToolRig.data_of(r_apply)["execution_id"])
    assert job_id in r_apply.summary
    assert len(r_apply.summary) <= SUMMARY_MAX

    r_val = rig.call("validate_part_graph", {"graph": _plate_graph()})
    assert len(r_val.summary) <= SUMMARY_MAX

    r_list = rig.call("list_feature_types", {})
    assert len(r_list.summary) <= SUMMARY_MAX

    r_schema = rig.call("get_feature_schema", {"types": ["sketch", "extrude", "cut_extrude"]})
    assert len(r_schema.summary) <= SUMMARY_MAX
