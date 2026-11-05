"""Contract tests for part operations, part.measure, and ErrorCode catalogue."""

from pathlib import Path
from typing import Any

from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated import ErrorCode

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
IPC_DIR = SCHEMAS_DIR / "ipc"

PART_CREATE_ID = "https://sw-mcp.invalid/schemas/ipc/ops/part.create.json"
SKETCH_CREATE_ID = "https://sw-mcp.invalid/schemas/ipc/ops/sketch.create.json"
FEATURE_CREATE_ID = "https://sw-mcp.invalid/schemas/ipc/ops/feature.create.json"
IPC_V0_ID = "https://sw-mcp.invalid/schemas/ipc/v0.json"
DOCUMENT_OPEN_ID = "https://sw-mcp.invalid/schemas/ipc/ops/document.open.json"


def _issues(instance: Any, schema_id: str) -> list[Any]:
    return list(validate_against_schema(instance, schema_id))


def test_part_verification_failed_in_error_codes() -> None:
    assert hasattr(ErrorCode, "PART_VERIFICATION_FAILED")
    assert ErrorCode.PART_VERIFICATION_FAILED == "PART_VERIFICATION_FAILED"


def test_part_create_schema_validates_fields() -> None:
    valid_params: dict[str, Any] = {
        "template": "D:\\templates\\ISO-mm.prtdot",
        "_meta": {"request_id": "req-1", "job_id": "job-1"},
    }
    assert _issues(valid_params, f"{PART_CREATE_ID}#/$defs/Params") == []

    valid_result: dict[str, Any] = {
        "native_id": 1,
        "path": "D:\\work\\plate.building.SLDPRT",
        "instance_id": "inst-abc",
        "previous_active": "D:\\other.SLDPRT",
        "template": {"path": "D:\\templates\\ISO-mm.prtdot", "sha256": "abcdef1234567890"},
    }
    assert _issues(valid_result, f"{PART_CREATE_ID}#/$defs/Result") == []

    # previous_active can be null
    valid_result_null_prev = dict(valid_result)
    valid_result_null_prev["previous_active"] = None
    assert _issues(valid_result_null_prev, f"{PART_CREATE_ID}#/$defs/Result") == []

    # missing required template in params
    assert _issues({}, f"{PART_CREATE_ID}#/$defs/Params") != []


def test_sketch_create_schema_validates_fields() -> None:
    valid_params = {
        "node_id": "sketch_base",
        "plane": "plane:front",
        "entities": [
            {"type": "line", "start": [-50.0, -30.0], "end": [50.0, -30.0]},
            {"type": "circle", "center": [0.0, 0.0], "diameter": 8.0},
        ],
    }
    assert _issues(valid_params, f"{SKETCH_CREATE_ID}#/$defs/Params") == []

    valid_result = {
        "native_id": 73,
        "feature_id": "f73",
        "entity_count": 2,
    }
    assert _issues(valid_result, f"{SKETCH_CREATE_ID}#/$defs/Result") == []

    # invalid plane
    invalid_plane = dict(valid_params, plane="plane:isometric")
    assert _issues(invalid_plane, f"{SKETCH_CREATE_ID}#/$defs/Params") != []


def test_feature_create_schema_validates_fields() -> None:
    valid_extrude = {
        "node_id": "extrude_base",
        "type": "extrude",
        "profile": "f73",
        "end_condition": {"type": "blind", "depth": 10.0},
    }
    assert _issues(valid_extrude, f"{FEATURE_CREATE_ID}#/$defs/Params") == []

    valid_cut = {
        "node_id": "cut_holes",
        "type": "cut_extrude",
        "profile": "f80",
        "end_condition": {"type": "through_all_both"},
    }
    assert _issues(valid_cut, f"{FEATURE_CREATE_ID}#/$defs/Params") == []

    valid_result = {
        "native_id": 79,
        "feature_id": "f79",
        "status": "ok",
    }
    assert _issues(valid_result, f"{FEATURE_CREATE_ID}#/$defs/Result") == []

    # invalid feature type
    assert (
        _issues(
            dict(valid_extrude, type="revolve"),
            f"{FEATURE_CREATE_ID}#/$defs/Params",
        )
        != []
    )


def test_part_measure_schema_carries_raw_si_fields() -> None:
    valid_params: dict[str, Any] = {
        "document": "D:\\work\\plate.SLDPRT",
    }
    assert _issues(valid_params, f"{IPC_V0_ID}#/$defs/PartMeasureParams") == []

    valid_result: dict[str, Any] = {
        "path": "D:\\work\\plate.SLDPRT",
        "instance_id": "inst-123",
        "solid_body_count": 1,
        "bbox_m": {
            "min": [-0.05, -0.03, 0.0],
            "max": [0.05, 0.03, 0.01],
        },
        "volume_m3": 5.798938e-05,
        "surface_area_m2": 0.015803,
        "center_of_mass_m": [0.0, 0.0, 0.005],
        "cylinders_m": [
            {"point": [-0.04, -0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
        ],
        "rebuild": {"ok": True, "errors": []},
        "features": [
            {"feature_id": "f73", "native_id": 73, "type": "ProfileFeature", "status": "ok"},
            {"feature_id": "f79", "native_id": 79, "type": "Extrusion", "status": "ok"},
        ],
        "dirty": False,
        "read_only": False,
    }
    assert _issues(valid_result, f"{IPC_V0_ID}#/$defs/PartMeasureResult") == []

    # Missing SI fields
    invalid_result: dict[str, Any] = dict(valid_result)
    del invalid_result["volume_m3"]
    assert _issues(invalid_result, f"{IPC_V0_ID}#/$defs/PartMeasureResult") != []


def test_document_open_result_gains_optional_instance_id() -> None:
    with_inst = {"owned": True, "instance_id": "inst-999"}
    assert _issues(with_inst, f"{DOCUMENT_OPEN_ID}#/$defs/Result") == []

    without_inst = {"owned": True}
    assert _issues(without_inst, f"{DOCUMENT_OPEN_ID}#/$defs/Result") == []
