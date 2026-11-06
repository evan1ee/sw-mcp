"""Live SOLIDWORKS part operations and measurement verification (ADR-059, ADR-062, ADR-064).

Owner gate:
- Active interactive SOLIDWORKS 2025+ with sw-mcp add-in loaded
- If no session is registered, these tests skip cleanly.
"""

import contextlib
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest
from cad_ir.generated.ipc import Operation, OperationGroup
from cad_protocol.backend import IpcBackend
from core_service.discovery import (
    NamedPipeBackendProvider,
    SessionInfo,
    discover_sessions,
    get_default_session_dir,
)

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Windows only"),
    pytest.mark.live,
]

OWNER_TEMPLATE = Path(r"D:\01_Data\ZZ_EPG Drawing templates\ISO-mm.prtdot")
INSTALLED_TEMPLATE = Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_part.prtdot")

PLATE_LENGTH_MM = 100.0
PLATE_WIDTH_MM = 60.0
PLATE_DEPTH_MM = 10.0
HOLE_DIAMETER_MM = 8.0
HOLE_RADIUS_M = 0.004
HOLE_COUNT = 4
EXPECTED_VOL_M3 = (60000.0 - 4.0 * math.pi * 16.0 * 10.0) * 1e-9
TOLERANCE_TIGHT = 1e-5
VOL_TOLERANCE_RATIO = 0.0005
CUT_VOL_TOLERANCE_RATIO = 0.005


def _get_live_session() -> SessionInfo:
    sessions = discover_sessions(get_default_session_dir())
    if not sessions:
        pytest.skip(
            "No live SOLIDWORKS session discovered in %LOCALAPPDATA%\\sw-mcp\\sessions. "
            "Requires active SOLIDWORKS interactive session with sw-mcp add-in loaded."
        )
    return sessions[0]


def _get_working_dir() -> Path:
    temp_dir = Path(os.environ.get("TEMP", ".")) / "sw-mcp-test"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _resolve_template() -> str:
    if OWNER_TEMPLATE.exists():
        return str(OWNER_TEMPLATE)
    if INSTALLED_TEMPLATE.exists():
        return str(INSTALLED_TEMPLATE)
    pytest.skip("Neither owner nor installed template found.")


def _safe_close(backend: IpcBackend, work_file: Path, job_id: str) -> None:
    with contextlib.suppress(Exception):
        close_op = Operation(
            operation_id=f"{job_id}:close",
            op="document.close",
            params={"path": str(work_file), "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(work_file), operations=(close_op,))])
    backend.close()
    if work_file.exists():
        work_file.unlink()


def _build_base_plate(backend: IpcBackend, work_file: Path, job_id: str, template: str) -> None:
    # 1. part.create
    op1 = Operation(
        operation_id=f"{job_id}:1",
        op="part.create",
        params={"template": template, "_meta": {"job_id": job_id}},
    )
    res1 = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op1,))])
    assert res1.outcomes[0].error is None

    # 2. sketch.create: base outline
    op2 = Operation(
        operation_id=f"{job_id}:2",
        op="sketch.create",
        params={
            "node_id": "sketch_base",
            "plane": "plane:front",
            "entities": [
                {"type": "line", "start": [-50.0, -30.0], "end": [50.0, -30.0]},
                {"type": "line", "start": [50.0, -30.0], "end": [50.0, 30.0]},
                {"type": "line", "start": [50.0, 30.0], "end": [-50.0, 30.0]},
                {"type": "line", "start": [-50.0, 30.0], "end": [-50.0, -30.0]},
            ],
            "_meta": {"job_id": job_id},
        },
    )
    res2 = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op2,))])
    assert res2.outcomes[0].error is None
    sk_id = cast(dict[str, Any], res2.outcomes[0].result)["feature_id"]

    # 3. feature.create: extrude 10 mm
    op3 = Operation(
        operation_id=f"{job_id}:3",
        op="feature.create",
        params={
            "node_id": "extrude_base",
            "type": "extrude",
            "profile": sk_id,
            "end_condition": {"type": "blind", "depth": PLATE_DEPTH_MM},
            "_meta": {"job_id": job_id},
        },
    )
    res3 = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op3,))])
    assert res3.outcomes[0].error is None


def test_build_plate_by_ops() -> None:
    """The acceptance plate (100x60x10 mm with 4x dia 8mm holes) builds and measures correctly."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))

    template = _resolve_template()
    job_id = f"job_plate_{int(time.time())}"
    work_file = _get_working_dir() / f"plate_{int(time.time())}.building.SLDPRT"
    if work_file.exists():
        work_file.unlink()

    try:
        _build_base_plate(backend, work_file, job_id, template)

        # 4. sketch.create: 4 holes
        op4 = Operation(
            operation_id=f"{job_id}:4",
            op="sketch.create",
            params={
                "node_id": "sketch_holes",
                "plane": "plane:front",
                "entities": [
                    {"type": "circle", "center": [-40.0, -20.0], "diameter": HOLE_DIAMETER_MM},
                    {"type": "circle", "center": [40.0, -20.0], "diameter": HOLE_DIAMETER_MM},
                    {"type": "circle", "center": [40.0, 20.0], "diameter": HOLE_DIAMETER_MM},
                    {"type": "circle", "center": [-40.0, 20.0], "diameter": HOLE_DIAMETER_MM},
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res4 = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op4,))])
        assert res4.outcomes[0].error is None
        sk_holes_id = cast(dict[str, Any], res4.outcomes[0].result)["feature_id"]

        # 5. feature.create: cut_extrude through_all_both
        op5 = Operation(
            operation_id=f"{job_id}:5",
            op="feature.create",
            params={
                "node_id": "cut_holes",
                "type": "cut_extrude",
                "profile": sk_holes_id,
                "end_condition": {"type": "through_all_both"},
                "_meta": {"job_id": job_id},
            },
        )
        res5 = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op5,))])
        assert res5.outcomes[0].error is None

        # 6. part.measure command
        measured = cast(dict[str, Any], backend.measure_part(str(work_file)))
        assert measured["solid_body_count"] == 1
        assert measured["rebuild"]["ok"] is True
        assert len(measured["rebuild"]["errors"]) == 0

        # Expected volume: 60,000 - 4 * pi * 4^2 * 10 = 57,989.38 mm3
        assert abs(measured["volume_m3"] - EXPECTED_VOL_M3) / EXPECTED_VOL_M3 < VOL_TOLERANCE_RATIO

        # Bounding box: [-0.05, -0.03, 0.0] to [0.05, 0.03, 0.01] within 0.01 mm
        bbox = cast(dict[str, Any], measured["bbox_m"])
        assert abs(bbox["min"][0] - (-0.05)) < TOLERANCE_TIGHT
        assert abs(bbox["min"][1] - (-0.03)) < TOLERANCE_TIGHT
        assert abs(bbox["min"][2] - 0.0) < TOLERANCE_TIGHT
        assert abs(bbox["max"][0] - 0.05) < TOLERANCE_TIGHT
        assert abs(bbox["max"][1] - 0.03) < TOLERANCE_TIGHT
        assert abs(bbox["max"][2] - 0.01) < TOLERANCE_TIGHT

        # 4 cylindrical faces with radius 4 mm
        cylinders = cast(list[dict[str, Any]], measured["cylinders_m"])
        assert len(cylinders) == HOLE_COUNT
        for cyl in cylinders:
            assert abs(cyl["radius"] - HOLE_RADIUS_M) < TOLERANCE_TIGHT

        # Features list
        features = cast(list[dict[str, Any]], measured["features"])
        feature_types = {f["type"] for f in features}
        assert "ProfileFeature" in feature_types
        assert "Extrusion" in feature_types
        assert "ICE" in feature_types
    finally:
        _safe_close(backend, work_file, job_id)


def test_missing_template_is_clear() -> None:
    """Missing template file produces FILE_NOT_FOUND error naming part.template."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))

    job_id = f"job_tmpl_missing_{int(time.time())}"
    work_file = _get_working_dir() / f"missing_{int(time.time())}.SLDPRT"
    nonexistent = r"C:\nonexistent\missing_template.prtdot"

    try:
        op = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": nonexistent, "_meta": {"job_id": job_id}},
        )
        res = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op,))])
        assert res.outcomes[0].error is not None
        assert res.outcomes[0].error.code == "FILE_NOT_FOUND"
        details = res.outcomes[0].error.details
        assert isinstance(details, dict)
        assert details.get("setting") == "part.template"
    finally:
        backend.close()


def test_part_create_refuses_existing_file() -> None:
    """part.create refuses an existing file path before SaveAs4 can overwrite it."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))

    template = _resolve_template()
    job_id = f"job_refuse_{int(time.time())}"
    existing_file = _get_working_dir() / f"already_exists_{int(time.time())}.SLDPRT"
    existing_file.write_text("dummy content", encoding="utf-8")

    try:
        op = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": template, "_meta": {"job_id": job_id}},
        )
        res = backend.apply_ops([OperationGroup(document=str(existing_file), operations=(op,))])
        assert res.outcomes[0].error is not None
        assert res.outcomes[0].error.code == "AUTH_SOURCE_WRITE_NOT_ALLOWED"
    finally:
        backend.close()
        if existing_file.exists():
            existing_file.unlink()


def test_blind_cut_goes_into_body() -> None:
    """A blind cut passes Dir=true to cut into the body (volume decreases)."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))

    template = _resolve_template()
    job_id = f"job_blind_{int(time.time())}"
    work_file = _get_working_dir() / f"blind_{int(time.time())}.building.SLDPRT"

    try:
        _build_base_plate(backend, work_file, job_id, template)

        measured_before = cast(dict[str, Any], backend.measure_part(str(work_file)))
        vol_before = cast(float, measured_before["volume_m3"])

        # Cut sketch (one circle at center, dia 10mm, radius 5mm)
        op4 = Operation(
            operation_id=f"{job_id}:4",
            op="sketch.create",
            params={
                "node_id": "sk_cut",
                "plane": "plane:front",
                "entities": [{"type": "circle", "center": [0.0, 0.0], "diameter": 10.0}],
                "_meta": {"job_id": job_id},
            },
        )
        r4 = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op4,))])
        assert r4.outcomes[0].error is None
        cut_sk_id = cast(dict[str, Any], r4.outcomes[0].result)["feature_id"]

        # Blind cut 4 mm deep
        cut_depth_mm = 4.0
        op5 = Operation(
            operation_id=f"{job_id}:5",
            op="feature.create",
            params={
                "node_id": "cut_blind",
                "type": "cut_extrude",
                "profile": cut_sk_id,
                "end_condition": {"type": "blind", "depth": cut_depth_mm},
                "_meta": {"job_id": job_id},
            },
        )
        r5 = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op5,))])
        assert r5.outcomes[0].error is None

        measured_after = cast(dict[str, Any], backend.measure_part(str(work_file)))
        vol_after = cast(float, measured_after["volume_m3"])

        # Volume removed = pi * r^2 * h = pi * (0.005)^2 * 0.004 m3
        expected_removed = math.pi * 0.005 * 0.005 * 0.004
        actual_removed = vol_before - vol_after
        assert abs(actual_removed - expected_removed) / expected_removed < CUT_VOL_TOLERANCE_RATIO
    finally:
        _safe_close(backend, work_file, job_id)


def test_null_feature_fails() -> None:
    """A feature operation that creates no valid geometry fails with error."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))

    template = _resolve_template()
    job_id = f"job_null_{int(time.time())}"
    work_file = _get_working_dir() / f"null_{int(time.time())}.building.SLDPRT"

    try:
        op1 = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": template, "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(work_file), operations=(op1,))])

        # Attempt to extrude an unresolved profile feature id
        op_bad = Operation(
            operation_id=f"{job_id}:2",
            op="feature.create",
            params={
                "node_id": "ext_bad",
                "type": "extrude",
                "profile": "f99999",
                "end_condition": {"type": "blind", "depth": 10.0},
                "_meta": {"job_id": job_id},
            },
        )
        res = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op_bad,))])
        assert res.outcomes[0].error is not None
        assert res.outcomes[0].error.code in ("IR_REFERENCE_UNRESOLVED", "BACKEND_REBUILD_ERROR")
    finally:
        _safe_close(backend, work_file, job_id)
