"""Live end-to-end acceptance tests for the Part Chain MVP (design 12 items 8 to 12e, Task 12).

Owner gate:
- Active interactive SOLIDWORKS 2025+ with sw-mcp add-in loaded and registered.
- If no session is registered in %LOCALAPPDATA%\\sw-mcp\\sessions, these tests skip cleanly.
"""

import contextlib
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, cast

import pytest
from cad_application.authoring_eval.references import REFERENCE_ANSWERS
from cad_application.authoring_guide import EXAMPLES
from cad_application.config.settings import ConfigError
from cad_application.jobs.part_files import failed_path, working_path
from cad_application.ports import Backend, BackendProvider
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import HelloResult, Meta, Operation, OperationGroup, OpsApplyResult
from cad_ir.part_feature_graph.model import PartGraph
from cad_ir.part_feature_graph.parse import parse_part_graph
from cad_protocol.backend import IpcBackend
from cad_verification import compare, expected_geometry
from core_service.discovery import (
    NamedPipeBackendProvider,
    SessionInfo,
    discover_sessions,
    get_default_session_dir,
)
from core_service.service import CoreService
from mcp_server.client import CorePipeClient

if sys.platform == "win32":
    import pythoncom  # type: ignore[import-not-found]
    import pywintypes  # type: ignore[import-not-found]
    import win32com.client  # type: ignore[import-not-found]
else:
    win32com = None  # type: ignore[assignment]

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Windows only"),
    pytest.mark.live,
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
PLATE_FIXTURE: Final = (
    REPO_ROOT / "tests" / "fixtures" / "schemas" / "part-feature-graph" / "valid" / "plate_4h.json"
)
OWNER_TEMPLATE: Final = Path(r"D:\01_Data\ZZ_EPG Drawing templates\ISO-mm.prtdot")
INSTALLED_TEMPLATE: Final = Path(
    r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_part.prtdot"
)

FINAL_STATES: Final = frozenset({"COMMITTED", "FAILED", "ABORTED"})
WAIT_POLL_MS: Final = 5000
MAX_STATUS_POLLS: Final = 24
WRONG_DEPTH_MM: Final = 9.0
SOLID_PLATE_VOL_M3: Final = 6.0e-5
SW_DOC_PART: Final = 1
SW_SAVE_AS_CURRENT_VERSION: Final = 0
SW_SAVE_AS_SILENT: Final = 1


def _com(obj: Any, name: str, *args: Any) -> Any:
    """Call a late-bound COM member that pywin32 may expose as a method or a property."""
    attr = getattr(obj, name)
    try:
        return attr(*args)
    except (TypeError, pywintypes.com_error):
        if args:
            raise
        return attr


def _plane_names(doc: Any) -> list[str]:
    names: list[str] = []
    feat = _com(doc, "FirstFeature")
    while feat is not None:
        if str(_com(feat, "GetTypeName2")) == "RefPlane":
            names.append(str(feat.Name))
        feat = _com(feat, "GetNextFeature")
    return names


def _save_as(doc: Any, path: str) -> bool:
    """SaveAs4 with by-reference error and warning outputs, as late binding requires."""
    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    return bool(doc.SaveAs4(path, SW_SAVE_AS_CURRENT_VERSION, SW_SAVE_AS_SILENT, errors, warnings))


SW_DONT_REBUILD_ACTIVE_DOC: Final = 1
SW_REORDER_BEFORE: Final = 1

type NotificationCallback = Callable[[str, JsonValue], None]


class DepthAlteringBackend:
    """Test-only Backend wrapper that alters a target node's depth in transit during apply_ops."""

    def __init__(
        self,
        inner: Backend,
        *,
        target_node: str = "extrude_base",
        new_depth: float = WRONG_DEPTH_MM,
    ) -> None:
        self._inner = inner
        self._target_node = target_node
        self._new_depth = new_depth

    @property
    def session(self) -> HelloResult:
        return self._inner.session

    def completed_operations(self) -> tuple[str, ...]:
        return self._inner.completed_operations()

    def snapshot_drawing(
        self,
        document: str,
        sheets: Sequence[str] | None = None,
        *,
        meta: Meta | None = None,
    ) -> JsonValue:
        return self._inner.snapshot_drawing(document, sheets, meta=meta)

    def measure_part(self, document: str, *, meta: Meta | None = None) -> JsonValue:
        return self._inner.measure_part(document, meta=meta)

    def apply_ops(
        self,
        groups: Sequence[OperationGroup],
        *,
        meta: Meta | None = None,
    ) -> OpsApplyResult:
        altered_groups: list[OperationGroup] = []
        for group in groups:
            altered_ops: list[Operation] = []
            for op in group.operations:
                if (
                    op.op == "feature.create"
                    and isinstance(op.params, dict)
                    and op.params.get("node_id") == self._target_node
                ):
                    new_params = dict(op.params)
                    end_cond = new_params.get("end_condition")
                    if isinstance(end_cond, dict):
                        new_end = dict(end_cond)
                        new_end["depth"] = self._new_depth
                        new_params["end_condition"] = new_end
                    altered_ops.append(replace(op, params=new_params))
                else:
                    altered_ops.append(op)
            altered_groups.append(replace(group, operations=tuple(altered_ops)))
        return self._inner.apply_ops(altered_groups, meta=meta)

    def cancel(self, *, meta: Meta | None = None) -> bool:
        return self._inner.cancel(meta=meta)

    def close(self) -> None:
        self._inner.close()


class DepthAlteringBackendProvider:
    """Test-only BackendProvider that wraps acquired backends in DepthAlteringBackend."""

    def __init__(
        self,
        inner: BackendProvider,
        *,
        target_node: str = "extrude_base",
        new_depth: float = WRONG_DEPTH_MM,
    ) -> None:
        self._inner = inner
        self._target_node = target_node
        self._new_depth = new_depth

    def acquire(self, on_notification: NotificationCallback) -> Backend:
        backend = self._inner.acquire(on_notification)
        return DepthAlteringBackend(
            backend,
            target_node=self._target_node,
            new_depth=self._new_depth,
        )


class _InterferingBackend:
    """Test-only Backend wrapper that invokes a callback after a specified operation completes."""

    def __init__(
        self,
        inner: Backend,
        *,
        after_node: str,
        callback: Callable[[str], None],
    ) -> None:
        self._inner = inner
        self._after_node = after_node
        self._callback = callback
        self._triggered = False

    @property
    def session(self) -> HelloResult:
        return self._inner.session

    def completed_operations(self) -> tuple[str, ...]:
        return self._inner.completed_operations()

    def snapshot_drawing(
        self,
        document: str,
        sheets: Sequence[str] | None = None,
        *,
        meta: Meta | None = None,
    ) -> JsonValue:
        return self._inner.snapshot_drawing(document, sheets, meta=meta)

    def measure_part(self, document: str, *, meta: Meta | None = None) -> JsonValue:
        return self._inner.measure_part(document, meta=meta)

    def apply_ops(
        self,
        groups: Sequence[OperationGroup],
        *,
        meta: Meta | None = None,
    ) -> OpsApplyResult:
        result = self._inner.apply_ops(groups, meta=meta)
        if not self._triggered:
            for group in groups:
                for op in group.operations:
                    if isinstance(op.params, dict) and op.params.get("node_id") == self._after_node:
                        self._triggered = True
                        self._callback(group.document)
                        break
        return result

    def cancel(self, *, meta: Meta | None = None) -> bool:
        return self._inner.cancel(meta=meta)

    def close(self) -> None:
        self._inner.close()


class _InterferingBackendProvider:
    def __init__(
        self,
        inner: BackendProvider,
        *,
        after_node: str,
        callback: Callable[[str], None],
    ) -> None:
        self._inner = inner
        self._after_node = after_node
        self._callback = callback

    def acquire(self, on_notification: NotificationCallback) -> Backend:
        return _InterferingBackend(
            self._inner.acquire(on_notification),
            after_node=self._after_node,
            callback=self._callback,
        )


def _get_live_session() -> SessionInfo:
    sessions = discover_sessions(get_default_session_dir())
    if not sessions:
        pytest.skip(
            "No live SOLIDWORKS session discovered in %LOCALAPPDATA%\\sw-mcp\\sessions. "
            "Requires active SOLIDWORKS interactive session with sw-mcp add-in loaded."
        )
    return sessions[0]


def _resolve_template() -> str:
    if OWNER_TEMPLATE.exists():
        return str(OWNER_TEMPLATE)
    if INSTALLED_TEMPLATE.exists():
        return str(INSTALLED_TEMPLATE)
    pytest.skip("Neither owner nor installed part template found.")


def _plate_graph() -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], json.loads(PLATE_FIXTURE.read_text(encoding="utf-8")))


def _prepare_env(
    base_dir: Path,
    *,
    allowed_roots: Sequence[Path],
    template_path: str,
    session: SessionInfo | None = None,
) -> dict[str, str]:
    appdata = base_dir / "appdata"
    local = base_dir / "local"
    config_dir = appdata / "sw-mcp"
    config_dir.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)

    roots_toml = ", ".join(json.dumps(str(r)) for r in allowed_roots)
    template_toml = json.dumps(template_path)
    config_text = (
        'config_version = "1.0"\n'
        f"[access]\nallowed_roots = [{roots_toml}]\n"
        f"[part]\ntemplate = {template_toml}\n"
    )
    (config_dir / "config.toml").write_text(config_text, encoding="utf-8")

    if session is not None:
        real_session_file = get_default_session_dir() / f"{session.pid}.json"
        if real_session_file.is_file():
            target_sessions_dir = local / "sw-mcp" / "sessions"
            target_sessions_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(real_session_file, target_sessions_dir / f"{session.pid}.json")

    return {
        "APPDATA": str(appdata),
        "LOCALAPPDATA": str(local),
    }


def _start_core(
    base_dir: Path,
    *,
    allowed_roots: Sequence[Path],
    template_path: str,
    provider: BackendProvider,
) -> CoreService:
    environ = _prepare_env(
        base_dir,
        allowed_roots=allowed_roots,
        template_path=template_path,
    )
    started = CoreService.start(
        install_root=str(REPO_ROOT),
        environ=environ,
        provider=provider,
    )
    if isinstance(started, ConfigError):
        raise AssertionError(f"CoreService failed to start: {started}")
    return started


def _call_ok(service: CoreService, name: str, arguments: dict[str, JsonValue]) -> dict[str, Any]:
    res = service.call_tool(name, arguments)
    envelope = res.envelope
    assert isinstance(envelope, dict), envelope
    assert envelope.get("ok") is True, envelope
    data = envelope.get("data")
    assert isinstance(data, dict), envelope
    return cast(dict[str, Any], data)


def _wait_for_job(service: CoreService, execution_id: str) -> dict[str, Any]:
    data = _call_ok(
        service,
        "get_execution_status",
        {"execution_id": execution_id, "wait_ms": 0},
    )
    for _ in range(MAX_STATUS_POLLS):
        if data.get("state") in FINAL_STATES:
            return data
        data = _call_ok(
            service,
            "get_execution_status",
            {"execution_id": execution_id, "wait_ms": WAIT_POLL_MS},
        )
    raise AssertionError(f"Job {execution_id} did not reach a final state: {data}")


def _close_in_solidworks_by_path(path: Path) -> None:
    if win32com is None:
        return
    with contextlib.suppress(Exception):
        sw_app = win32com.client.Dispatch("SldWorks.Application")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if sw_app.GetOpenDocumentByName(str(path)) is not None:  # type: ignore[reportUnknownMemberType]
            sw_app.CloseDoc(str(path))  # type: ignore[reportUnknownMemberType]


def test_plate_end_to_end(tmp_path: Path) -> None:
    """Design 12 item 8: reach COMMITTED, then open the target read-only and measure it again."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_e2e.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target)},
        )
        job_id = str(applied["execution_id"])
        final = _wait_for_job(service, job_id)
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        assert part_result["path"] == str(target)
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks)
        feature_ids = cast(dict[str, str], part_result["feature_ids"])
    finally:
        service.stop()

    # Separate read-only reopen and measurement outside the job
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))
    verify_job_id = f"job_verify_{int(time.time())}"
    try:
        open_op = Operation(
            operation_id=f"{verify_job_id}:1",
            op="document.open",
            params={
                "path": str(target),
                "read_only": True,
                "fully_resolved": True,
                "_meta": {"job_id": verify_job_id},
            },
        )
        open_res = backend.apply_ops([OperationGroup(document=str(target), operations=(open_op,))])
        assert open_res.outcomes[0].error is None

        measured = cast(dict[str, Any], backend.measure_part(str(target)))
        assert measured["read_only"] is True
        assert measured["dirty"] is False

        parsed_graph = parse_part_graph(_plate_graph())
        assert isinstance(parsed_graph, PartGraph)
        expected = expected_geometry(parsed_graph)
        reopen_checks = compare(expected, measured, feature_ids)
        assert all(c.passed for c in reopen_checks), reopen_checks
    finally:
        with contextlib.suppress(Exception):
            close_op = Operation(
                operation_id=f"{verify_job_id}:2",
                op="document.close",
                params={"path": str(target), "_meta": {"job_id": verify_job_id}},
            )
            backend.apply_ops([OperationGroup(document=str(target), operations=(close_op,))])
        backend.close()


def _top_face_hole_graph() -> dict[str, JsonValue]:
    """A 40 x 30 x 10 mm block with a 5 mm hole, 4 mm deep, in the middle of its end (top) face."""
    return cast(dict[str, JsonValue], EXAMPLES["block_top_hole"].graph)


def _cap_face_hole_graph(
    base_plane: str = "plane:front",
    cap_role: str = "end_face",
    center: tuple[float, float] = (10.0, 5.0),
) -> dict[str, JsonValue]:
    """Build a 40x30x10 mm block on ``base_plane`` with a 5x4 mm blind hole on ``cap_role``."""
    graph = copy.deepcopy(EXAMPLES["block_top_hole"].graph)
    graph["id"] = f"block_{base_plane.split(':')[1]}_{cap_role}"
    graph["nodes"]["sketch_base"]["plane"] = base_plane
    graph["nodes"]["sketch_hole"]["plane"] = f"extrude_base.{cap_role}"
    graph["nodes"]["sketch_hole"]["entities"]["c1"]["center"] = [center[0], center[1]]
    return cast(dict[str, JsonValue], graph)


def _block_centre_hole_graph() -> dict[str, JsonValue]:
    """Return the block_centre_hole benchmark fixture (40x30x10 mm block, 5 mm through-hole)."""
    raw = REFERENCE_ANSWERS["block_centre_hole"]
    assert raw is not None
    return cast(dict[str, JsonValue], copy.deepcopy(raw))


def test_blind_hole_in_top_face(tmp_path: Path) -> None:
    """ADR-070: a sketch on the end face, a blind cut into the body, then a read-only reopen."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "block_top_hole.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _top_face_hole_graph(), "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        print("FINAL RESULT:", json.dumps(final, indent=2))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_blind_hole_in_start_face(tmp_path: Path) -> None:
    """ADR-070 / Debt 2: a sketch on extrude_base.start_face with a blind cut into the body."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "block_start_hole.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {
                "graph": _cap_face_hole_graph("plane:front", "start_face"),
                "target_path": str(target),
            },
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        print("FINAL RESULT:", json.dumps(final, indent=2))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


@pytest.mark.parametrize(
    ("base_plane", "cap_role"),
    [
        ("plane:top", "end_face"),
        ("plane:top", "start_face"),
        ("plane:right", "end_face"),
        ("plane:right", "start_face"),
    ],
)
def test_blind_hole_on_non_front_base_planes(
    tmp_path: Path, base_plane: str, cap_role: str
) -> None:
    """ADR-070 / K29 / Debt 2: cap-face blind holes on parts built on plane:top and plane:right."""
    session = _get_live_session()
    template = _resolve_template()
    plane_slug = base_plane.split(":")[1]
    proj = tmp_path / f"proj_{plane_slug}_{cap_role}"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / f"block_{plane_slug}_{cap_role}.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {
                "graph": _cap_face_hole_graph(base_plane, cap_role),
                "target_path": str(target),
            },
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        print("FINAL RESULT:", json.dumps(final, indent=2))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_block_centre_hole_end_to_end(tmp_path: Path) -> None:
    """Debt 2: verify the block_centre_hole benchmark fixture end-to-end against live SOLIDWORKS."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "block_centre_hole.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _block_centre_hole_graph(), "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        print("FINAL RESULT:", json.dumps(final, indent=2))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_wrong_plan_fails(tmp_path: Path) -> None:
    """Design 12 item 9: provider alters depth to 9 in transit; job ends FAILED, .failed kept."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_wrong_depth.SLDPRT"

    base_provider = NamedPipeBackendProvider(target_session=str(session.pid))
    provider = DepthAlteringBackendProvider(
        base_provider,
        target_node="extrude_base",
        new_depth=WRONG_DEPTH_MM,
    )
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    job_id = ""
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target)},
        )
        job_id = str(applied["execution_id"])
        final = _wait_for_job(service, job_id)
        assert final["state"] == "FAILED", final
        error = cast(dict[str, Any], final["error"])
        assert error["code"] == "PART_VERIFICATION_FAILED"
        assert not target.exists()

        expected_failed = Path(failed_path(str(target), job_id))
        assert expected_failed.is_file()
        details = cast(dict[str, Any], error["details"])
        assert details.get("failed_path") == str(expected_failed)
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)
        if job_id:
            _close_in_solidworks_by_path(Path(working_path(str(target), job_id)))
            _close_in_solidworks_by_path(Path(failed_path(str(target), job_id)))


def test_second_job_same_core(tmp_path: Path) -> None:
    """Design 12 item 10 (F7): two consecutive part jobs in the same CoreService succeed."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target1 = proj / "plate_first.SLDPRT"
    target2 = proj / "plate_second.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied1 = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target1)},
        )
        final1 = _wait_for_job(service, str(applied1["execution_id"]))
        assert final1["state"] == "COMMITTED", final1
        assert target1.is_file()

        applied2 = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target2)},
        )
        final2 = _wait_for_job(service, str(applied2["execution_id"]))
        assert final2["state"] == "COMMITTED", final2
        assert target2.is_file()
    finally:
        service.stop()
        _close_in_solidworks_by_path(target1)
        _close_in_solidworks_by_path(target2)


def test_open_dirty_document_untouched(tmp_path: Path) -> None:
    """Design 12 item 11 (F4, F5): an open unsaved scratch document stays open and active."""
    session = _get_live_session()
    template = _resolve_template()
    if win32com is None:
        pytest.skip("win32com not available")

    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    scratch_dirty = tmp_path / "engineer_dirty_scratch.SLDPRT"
    target = proj / "plate_while_dirty_open.SLDPRT"

    sw_app = win32com.client.Dispatch("SldWorks.Application")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
    doc = sw_app.NewDocument(template, 0, 0, 0)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert doc is not None
    try:
        saved = _save_as(doc, str(scratch_dirty))
        assert saved
        hash_before = hashlib.sha256(scratch_dirty.read_bytes()).hexdigest()

        # Make the engineer's scratch document dirty with an unsaved sketch line and keep it active
        sw_app.ActivateDoc3(  # type: ignore[reportUnknownMemberType]
            str(scratch_dirty),
            False,
            SW_DONT_REBUILD_ACTIVE_DOC,
            win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0),
        )
        sm = doc.SketchManager  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        sm.InsertSketch(True)  # type: ignore[reportUnknownMemberType]
        sm.CreateLine(0.0, 0.0, 0.0, 0.02, 0.02, 0.0)  # type: ignore[reportUnknownMemberType]
        sm.InsertSketch(True)  # type: ignore[reportUnknownMemberType]
        assert bool(_com(doc, "GetSaveFlag")) is True  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]

        provider = NamedPipeBackendProvider(target_session=str(session.pid))
        service = _start_core(
            tmp_path,
            allowed_roots=(proj,),
            template_path=template,
            provider=provider,
        )
        try:
            applied = _call_ok(
                service,
                "apply_part_graph",
                {"graph": _plate_graph(), "target_path": str(target)},
            )
            final = _wait_for_job(service, str(applied["execution_id"]))
            assert final["state"] == "COMMITTED", final
            assert target.is_file()
        finally:
            service.stop()

        # Engineer's scratch document is still open, still dirty, un-overwritten on disk, and active
        still_open = sw_app.GetOpenDocumentByName(str(scratch_dirty))  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        assert still_open is not None
        assert bool(_com(still_open, "GetSaveFlag")) is True  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        assert hashlib.sha256(scratch_dirty.read_bytes()).hexdigest() == hash_before

        active_doc = sw_app.ActiveDoc  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        assert active_doc is not None
        active_path = str(_com(active_doc, "GetPathName"))  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        assert os.path.normcase(active_path) == os.path.normcase(str(scratch_dirty))
    finally:
        _close_in_solidworks_by_path(scratch_dirty)


def test_unknown_op_fails_batch(tmp_path: Path) -> None:
    """Design 12 item 12 (F6): an unknown operation fails its batch with capability missing."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))
    work_file = tmp_path / "unknown_op.SLDPRT"
    try:
        unknown_op = Operation(
            operation_id=f"job_unknown_{int(time.time())}:1",
            op="part.unknown_operation",
            params={},
        )
        res = backend.apply_ops([OperationGroup(document=str(work_file), operations=(unknown_op,))])
        assert res.outcomes[0].error is not None
        assert res.outcomes[0].error.code == "BACKEND_CAPABILITY_MISSING"
    finally:
        backend.close()


@pytest.mark.parametrize("action", ["edit", "save", "close"])
def test_engineer_interference(tmp_path: Path, action: str) -> None:
    """Design 12 item 12a: an engineer's edit, save or close mid-job fails the job with no target.

    Note: Spike answer 9 proved that active-document switching does not affect feature calls,
    so interference covers edit (regen), save, and close on the working part.
    """
    session = _get_live_session()
    template = _resolve_template()
    if win32com is None:
        pytest.skip("win32com not available")

    proj = tmp_path / f"proj_{action}"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / f"plate_{action}.SLDPRT"
    touched_docs: list[str] = []

    def _interfere(work_doc_path: str) -> None:
        touched_docs.append(work_doc_path)
        sw_app = win32com.client.Dispatch("SldWorks.Application")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        model = sw_app.GetOpenDocumentByName(work_doc_path)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        assert model is not None
        if action == "edit":
            model.ForceRebuild3(False)  # type: ignore[reportUnknownMemberType]
        elif action == "save":
            model.SaveAs4(  # type: ignore[reportUnknownMemberType]
                work_doc_path,
                SW_SAVE_AS_CURRENT_VERSION,
                SW_SAVE_AS_SILENT,
                0,
                0,
            )
        elif action == "close":
            sw_app.CloseDoc(work_doc_path)  # type: ignore[reportUnknownMemberType]
        time.sleep(0.3)

    base_provider = NamedPipeBackendProvider(target_session=str(session.pid))
    provider = _InterferingBackendProvider(
        base_provider,
        after_node="extrude_base",
        callback=_interfere,
    )
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target)},
        )
        job_id = str(applied["execution_id"])
        final = _wait_for_job(service, job_id)
        assert final["state"] == "FAILED", final
        assert not target.exists()
    finally:
        service.stop()
        for doc_path in touched_docs:
            _close_in_solidworks_by_path(Path(doc_path))


def _build_plate_via_ops(backend: IpcBackend, work_file: Path, job_id: str, template: str) -> str:
    """Create a 100x60x10 mm base plate via IPC ops and return its instance_id."""
    op_create = Operation(
        operation_id=f"{job_id}:1",
        op="part.create",
        params={"template": template, "_meta": {"job_id": job_id}},
    )
    res_create = backend.apply_ops(
        [OperationGroup(document=str(work_file), operations=(op_create,))]
    )
    assert res_create.outcomes[0].error is None
    inst_id = str(cast(dict[str, Any], res_create.outcomes[0].result)["instance_id"])

    op_sk = Operation(
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
    res_sk = backend.apply_ops([OperationGroup(document=str(work_file), operations=(op_sk,))])
    sk_id = str(cast(dict[str, Any], res_sk.outcomes[0].result)["feature_id"])

    op_ext = Operation(
        operation_id=f"{job_id}:3",
        op="feature.create",
        params={
            "node_id": "extrude_base",
            "type": "extrude",
            "profile": sk_id,
            "end_condition": {"type": "blind", "depth": 10.0},
            "_meta": {"job_id": job_id},
        },
    )
    backend.apply_ops([OperationGroup(document=str(work_file), operations=(op_ext,))])
    return inst_id


def test_reopen_is_new_instance(tmp_path: Path) -> None:
    """Design 12 item 12b: reopening gives a new instance_id and reads geometry from disk."""
    session = _get_live_session()
    template = _resolve_template()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))

    job_id = f"job_reopen_{int(time.time())}"
    part_a = tmp_path / "part_a.SLDPRT"
    part_b = tmp_path / "part_b.SLDPRT"

    try:
        inst_1 = _build_plate_via_ops(backend, part_a, job_id, template)
        op_save_a = Operation(
            operation_id=f"{job_id}:4",
            op="document.save",
            params={"path": str(part_a), "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(part_a), operations=(op_save_a,))])
        shutil.copy2(part_a, part_b)

        # Add a hole to part_a, save, and close
        op_hole_sk = Operation(
            operation_id=f"{job_id}:5",
            op="sketch.create",
            params={
                "node_id": "sketch_hole",
                "plane": "plane:front",
                "entities": [{"type": "circle", "center": [0.0, 0.0], "diameter": 8.0}],
                "_meta": {"job_id": job_id},
            },
        )
        res_hole_sk = backend.apply_ops(
            [OperationGroup(document=str(part_a), operations=(op_hole_sk,))]
        )
        hole_sk_id = cast(dict[str, Any], res_hole_sk.outcomes[0].result)["feature_id"]

        op_cut = Operation(
            operation_id=f"{job_id}:6",
            op="feature.create",
            params={
                "node_id": "cut_hole",
                "type": "cut_extrude",
                "profile": hole_sk_id,
                "end_condition": {"type": "through_all_both"},
                "_meta": {"job_id": job_id},
            },
        )
        backend.apply_ops([OperationGroup(document=str(part_a), operations=(op_cut,))])
        op_save_a2 = Operation(
            operation_id=f"{job_id}:7",
            op="document.save",
            params={"path": str(part_a), "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(part_a), operations=(op_save_a2,))])

        op_close_1 = Operation(
            operation_id=f"{job_id}:8",
            op="document.close",
            params={"path": str(part_a), "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(part_a), operations=(op_close_1,))])

        # Reopen part_a read-only: new instance_id
        op_open_2 = Operation(
            operation_id=f"{job_id}:9",
            op="document.open",
            params={
                "path": str(part_a),
                "read_only": True,
                "fully_resolved": True,
                "_meta": {"job_id": job_id},
            },
        )
        res_open_2 = backend.apply_ops(
            [OperationGroup(document=str(part_a), operations=(op_open_2,))]
        )
        inst_2 = cast(dict[str, Any], res_open_2.outcomes[0].result)["instance_id"]
        assert inst_2 != inst_1

        meas_2 = cast(dict[str, Any], backend.measure_part(str(part_a)))
        assert meas_2["instance_id"] == inst_2
        assert len(cast(list[Any], meas_2["cylinders_m"])) == 1

        op_close_2 = Operation(
            operation_id=f"{job_id}:10",
            op="document.close",
            params={"path": str(part_a), "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(part_a), operations=(op_close_2,))])

        # Replace part_a on disk with part_b (no holes) while closed, then reopen
        shutil.copy2(part_b, part_a)
        op_open_3 = Operation(
            operation_id=f"{job_id}:11",
            op="document.open",
            params={
                "path": str(part_a),
                "read_only": True,
                "fully_resolved": True,
                "_meta": {"job_id": job_id},
            },
        )
        backend.apply_ops([OperationGroup(document=str(part_a), operations=(op_open_3,))])
        meas_3 = cast(dict[str, Any], backend.measure_part(str(part_a)))
        assert len(cast(list[Any], meas_3["cylinders_m"])) == 0
        assert meas_3["volume_m3"] == pytest.approx(SOLID_PLATE_VOL_M3, rel=1e-4)
    finally:
        with contextlib.suppress(Exception):
            op_close_final = Operation(
                operation_id=f"{job_id}:99",
                op="document.close",
                params={"path": str(part_a), "_meta": {"job_id": job_id}},
            )
            backend.apply_ops([OperationGroup(document=str(part_a), operations=(op_close_final,))])
        backend.close()


def test_template_with_reordered_planes(tmp_path: Path) -> None:
    """Design 12 item 12c: a template whose standard RefPlane normals do not match fails clearly."""
    session = _get_live_session()
    template = _resolve_template()
    if win32com is None:
        pytest.skip("win32com not available")

    bad_template = tmp_path / "reordered_planes.prtdot"
    sw_app = win32com.client.Dispatch("SldWorks.Application")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
    doc = sw_app.NewDocument(template, 0, 0, 0)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert doc is not None
    initial_title = str(_com(doc, "GetTitle"))  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    try:
        # Collect standard RefPlanes and reorder Top before Front (or delete Front)
        planes: list[Any] = []
        feat = _com(doc, "FirstFeature")
        while feat is not None:
            if str(_com(feat, "GetTypeName2")) == "RefPlane":  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                planes.append(feat)
            feat = _com(feat, "GetNextFeature")

        assert len(planes) >= 2  # noqa: PLR2004
        front_name = str(planes[0].Name)  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        top_name = str(planes[1].Name)  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        reordered = bool(
            doc.Extension.ReorderFeature(top_name, front_name, SW_REORDER_BEFORE)  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )
        if not reordered:
            # If SOLIDWORKS refuses to reorder standard planes, delete first plane so Top is index 0
            planes[0].Select2(False, 0)
            doc.EditDelete()  # type: ignore[reportUnknownMemberType]
            if _plane_names(doc) == [str(p.Name) for p in planes]:
                pytest.skip("SOLIDWORKS refuses to reorder or delete standard planes")

        saved = _save_as(doc, str(bad_template))
        assert saved
    finally:
        with contextlib.suppress(Exception):
            sw_app.CloseDoc(str(bad_template))  # type: ignore[reportUnknownMemberType]
            sw_app.CloseDoc(initial_title)  # type: ignore[reportUnknownMemberType]

    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_reordered_tmpl.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path,
        allowed_roots=(proj,),
        template_path=str(bad_template),
        provider=provider,
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        assert final["state"] == "FAILED", final
        error = cast(dict[str, Any], final["error"])
        assert error["code"] == "BACKEND_OPERATION_FAILED"
        assert not target.exists()
    finally:
        service.stop()


def test_template_with_extra_feature(tmp_path: Path) -> None:
    """Design 12 item 12c: a template containing an extra feature fails feature verification."""
    session = _get_live_session()
    template = _resolve_template()
    if win32com is None:
        pytest.skip("win32com not available")

    extra_template = tmp_path / "extra_feature.prtdot"
    sw_app = win32com.client.Dispatch("SldWorks.Application")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
    doc = sw_app.NewDocument(template, 0, 0, 0)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
    assert doc is not None
    initial_title = str(_com(doc, "GetTitle"))  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    try:
        # Select first RefPlane and insert an extra sketch into the template
        feat = _com(doc, "FirstFeature")
        while feat is not None:
            if str(_com(feat, "GetTypeName2")) == "RefPlane":  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                feat.Select2(False, 0)  # type: ignore[reportUnknownMemberType]
                break
            feat = _com(feat, "GetNextFeature")

        sm = doc.SketchManager  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        sm.InsertSketch(True)  # type: ignore[reportUnknownMemberType]
        sm.CreateLine(0.0, 0.0, 0.0, 0.01, 0.0, 0.0)  # type: ignore[reportUnknownMemberType]
        sm.InsertSketch(True)  # type: ignore[reportUnknownMemberType]

        saved = _save_as(doc, str(extra_template))
        assert saved
    finally:
        with contextlib.suppress(Exception):
            sw_app.CloseDoc(str(extra_template))  # type: ignore[reportUnknownMemberType]
            sw_app.CloseDoc(initial_title)  # type: ignore[reportUnknownMemberType]

    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_extra_feat_tmpl.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path,
        allowed_roots=(proj,),
        template_path=str(extra_template),
        provider=provider,
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        assert final["state"] == "FAILED", final
        error = cast(dict[str, Any], final["error"])
        assert error["code"] == "PART_VERIFICATION_FAILED"
        details = cast(dict[str, Any], error["details"])
        assert "features" in cast(list[Any], details.get("checks", []))
        assert not target.exists()
    finally:
        service.stop()


def _spawn_and_kill_core_mid_job(
    proc_env: dict[str, str], core_session_file: Path, target: Path
) -> str:
    """Spawn sw-mcp-core, submit a part job, and taskkill the core once the working file exists."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "core_service"],
        env=proc_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    job_id = ""
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not core_session_file.is_file():
            time.sleep(0.05)
        assert core_session_file.is_file()

        client = CorePipeClient(env=proc_env, auto_start=False)
        client.connect()
        try:
            res = client.call_tool(
                "apply_part_graph",
                {"graph": _plate_graph(), "target_path": str(target)},
            )
            envelope = cast(dict[str, Any], res.get("envelope", res))
            assert envelope.get("ok") is True, envelope
            job_id = str(cast(dict[str, Any], envelope["data"])["execution_id"])
        finally:
            client.close()

        work_file = Path(working_path(str(target), job_id))
        wait_deadline = time.monotonic() + 15.0
        while time.monotonic() < wait_deadline and not work_file.exists():
            time.sleep(0.05)

        subprocess.run(
            ["taskkill", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    return job_id


def test_core_killed_mid_job(tmp_path: Path) -> None:
    """Design 12 item 12d: taskkill core mid-job; target stays absent, new core recovers."""
    session = _get_live_session()
    template = _resolve_template()

    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_killed.SLDPRT"

    custom_env = _prepare_env(
        tmp_path,
        allowed_roots=(proj,),
        template_path=template,
        session=session,
    )
    proc_env = {**os.environ, **custom_env}
    core_session_file = Path(custom_env["LOCALAPPDATA"]) / "sw-mcp" / "core.json"

    job_id = _spawn_and_kill_core_mid_job(proc_env, core_session_file, target)
    assert not target.exists()

    # Deal with the orphaned working part before starting the replacement job
    if job_id:
        work_file = Path(working_path(str(target), job_id))
        _close_in_solidworks_by_path(work_file)
        if work_file.exists():
            for _ in range(20):
                try:
                    work_file.unlink()
                    break
                except PermissionError:
                    time.sleep(0.1)

    # Start a new CoreService on the same store: recovers the interrupted job and runs a new one
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    new_service = CoreService.start(
        install_root=str(REPO_ROOT),
        environ=custom_env,
        provider=provider,
    )
    assert not isinstance(new_service, ConfigError)
    try:
        recovered = _call_ok(
            new_service,
            "get_execution_status",
            {"execution_id": job_id, "wait_ms": 0},
        )
        assert recovered["state"] == "FAILED", recovered
        err = cast(dict[str, Any], recovered["error"])
        assert err["code"] == "EXEC_INTERRUPTED"

        # Next job runs cleanly
        applied_next = _call_ok(
            new_service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target)},
        )
        final_next = _wait_for_job(new_service, str(applied_next["execution_id"]))
        assert final_next["state"] == "COMMITTED", final_next
        assert target.is_file()
    finally:
        new_service.stop()
        _close_in_solidworks_by_path(target)


def test_non_ascii_path(tmp_path: Path) -> None:
    """Design 12 item 12e: a target under a folder named '零件' reaches COMMITTED."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    cn_folder = proj / "零件"
    cn_folder.mkdir(parents=True, exist_ok=True)
    target = cn_folder / "plate.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": _plate_graph(), "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        print("FINAL RESULT:", json.dumps(final, indent=2))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_live_slot_plate(tmp_path: Path) -> None:
    """Verify the plate_slot benchmark fixture (arcs + lines) end-to-end against live SOLIDWORKS."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_slot.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": REFERENCE_ANSWERS["plate_slot"], "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_live_rectangle_plate(tmp_path: Path) -> None:
    """Verify rectangle entities end-to-end against live SOLIDWORKS."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_rectangles.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": REFERENCE_ANSWERS["plate_rectangles"], "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_live_direct_rectangle_ops(tmp_path: Path) -> None:
    """Verify direct IPC sketch.create with center_rectangle and corner_rectangle."""
    session = _get_live_session()
    template = _resolve_template()
    target = tmp_path / "direct_rect.SLDPRT"
    job_id = f"live_rect_{time.time_ns()}"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))
    try:
        op_create = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": template, "_meta": {"job_id": job_id}},
        )
        res_create = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_create,))]
        )
        assert res_create.outcomes[0].error is None

        op_sk_base = Operation(
            operation_id=f"{job_id}:2",
            op="sketch.create",
            params={
                "node_id": "sk_base",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "center_rectangle",
                        "center": [0.0, 0.0],
                        "width": 80.0,
                        "height": 50.0,
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_base = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_base,))]
        )
        assert res_sk_base.outcomes[0].error is None
        base_sk_id = str(cast(dict[str, Any], res_sk_base.outcomes[0].result)["feature_id"])

        op_ext = Operation(
            operation_id=f"{job_id}:3",
            op="feature.create",
            params={
                "node_id": "ext_base",
                "type": "extrude",
                "profile": base_sk_id,
                "end_condition": {"type": "blind", "depth": 10.0},
                "_meta": {"job_id": job_id},
            },
        )
        res_ext = backend.apply_ops([OperationGroup(document=str(target), operations=(op_ext,))])
        assert res_ext.outcomes[0].error is None

        op_sk_cut = Operation(
            operation_id=f"{job_id}:4",
            op="sketch.create",
            params={
                "node_id": "sk_cut",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "corner_rectangle",
                        "corner1": [-15.0, -10.0],
                        "corner2": [15.0, 10.0],
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_cut = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_cut,))]
        )
        assert res_sk_cut.outcomes[0].error is None
        cut_sk_id = str(cast(dict[str, Any], res_sk_cut.outcomes[0].result)["feature_id"])

        op_cut = Operation(
            operation_id=f"{job_id}:5",
            op="feature.create",
            params={
                "node_id": "cut_rect",
                "type": "cut_extrude",
                "profile": cut_sk_id,
                "end_condition": {"type": "through_all_both"},
                "_meta": {"job_id": job_id},
            },
        )
        res_cut = backend.apply_ops([OperationGroup(document=str(target), operations=(op_cut,))])
        assert res_cut.outcomes[0].error is None

        meas = cast(dict[str, Any], backend.measure_part(str(target)))
        # Expected volume: (80*50 - 30*20) * 10 = 34,000 mm3 = 3.4e-5 m3
        assert meas["volume_m3"] == pytest.approx(3.4e-5, rel=1e-3)
    finally:
        backend.close()
        _close_in_solidworks_by_path(target)


def test_live_direct_slot_ops(tmp_path: Path) -> None:
    """Verify direct IPC sketch.create with straight_slot."""
    session = _get_live_session()
    template = _resolve_template()
    target = tmp_path / "direct_slot.SLDPRT"
    job_id = f"live_slot_{time.time_ns()}"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))
    try:
        op_create = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": template, "_meta": {"job_id": job_id}},
        )
        res_create = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_create,))]
        )
        assert res_create.outcomes[0].error is None

        op_sk_base = Operation(
            operation_id=f"{job_id}:2",
            op="sketch.create",
            params={
                "node_id": "sk_base",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "straight_slot",
                        "start_point": [-20.0, 0.0],
                        "end_point": [20.0, 0.0],
                        "width": 20.0,
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_base = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_base,))]
        )
        assert res_sk_base.outcomes[0].error is None
        base_sk_id = str(cast(dict[str, Any], res_sk_base.outcomes[0].result)["feature_id"])

        op_ext = Operation(
            operation_id=f"{job_id}:3",
            op="feature.create",
            params={
                "node_id": "ext_base",
                "type": "extrude",
                "profile": base_sk_id,
                "end_condition": {"type": "blind", "depth": 10.0},
                "_meta": {"job_id": job_id},
            },
        )
        res_ext = backend.apply_ops([OperationGroup(document=str(target), operations=(op_ext,))])
        assert res_ext.outcomes[0].error is None

        meas = cast(dict[str, Any], backend.measure_part(str(target)))
        # Expected volume: (40 * 20 + pi * 10^2) * 10 = (800 + 100 * pi) * 10 mm3
        expected_vol = (800.0 + math.pi * 100.0) * 10.0 * 1e-9
        assert meas["volume_m3"] == pytest.approx(expected_vol, rel=1e-3)
    finally:
        backend.close()
        _close_in_solidworks_by_path(target)


def test_live_linear_pattern_plate(tmp_path: Path) -> None:
    """Verify linear pattern feature end-to-end against live SOLIDWORKS."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_pattern_holes.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": REFERENCE_ANSWERS["plate_pattern_holes"], "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_live_direct_linear_pattern_ops(tmp_path: Path) -> None:
    """Verify direct IPC feature.create with linear_pattern."""
    session = _get_live_session()
    template = _resolve_template()
    target = tmp_path / "direct_lpattern.SLDPRT"
    job_id = f"live_lpattern_{time.time_ns()}"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))
    try:
        op_create = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": template, "_meta": {"job_id": job_id}},
        )
        res_create = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_create,))]
        )
        assert res_create.outcomes[0].error is None

        op_sk_base = Operation(
            operation_id=f"{job_id}:2",
            op="sketch.create",
            params={
                "node_id": "sk_base",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "center_rectangle",
                        "center": [0.0, 0.0],
                        "width": 100.0,
                        "height": 60.0,
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_base = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_base,))]
        )
        assert res_sk_base.outcomes[0].error is None
        base_sk_id = str(cast(dict[str, Any], res_sk_base.outcomes[0].result)["feature_id"])

        op_ext = Operation(
            operation_id=f"{job_id}:3",
            op="feature.create",
            params={
                "node_id": "ext_base",
                "type": "extrude",
                "profile": base_sk_id,
                "end_condition": {"type": "blind", "depth": 10.0},
                "_meta": {"job_id": job_id},
            },
        )
        res_ext = backend.apply_ops([OperationGroup(document=str(target), operations=(op_ext,))])
        assert res_ext.outcomes[0].error is None

        op_sk_hole = Operation(
            operation_id=f"{job_id}:4",
            op="sketch.create",
            params={
                "node_id": "sk_hole",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "circle",
                        "center": [-30.0, 0.0],
                        "diameter": 10.0,
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_hole = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_hole,))]
        )
        assert res_sk_hole.outcomes[0].error is None
        hole_sk_id = str(cast(dict[str, Any], res_sk_hole.outcomes[0].result)["feature_id"])

        op_cut = Operation(
            operation_id=f"{job_id}:5",
            op="feature.create",
            params={
                "node_id": "cut_hole",
                "type": "cut_extrude",
                "profile": hole_sk_id,
                "end_condition": {"type": "through_all_both"},
                "_meta": {"job_id": job_id},
            },
        )
        res_cut = backend.apply_ops([OperationGroup(document=str(target), operations=(op_cut,))])
        assert res_cut.outcomes[0].error is None
        cut_id = str(cast(dict[str, Any], res_cut.outcomes[0].result)["feature_id"])

        op_pat = Operation(
            operation_id=f"{job_id}:6",
            op="feature.create",
            params={
                "node_id": "pat_holes",
                "type": "linear_pattern",
                "seeds": [cut_id],
                "direction_1": {
                    "direction": "plane:right",
                    "spacing": 20.0,
                    "count": 4,
                },
                "_meta": {"job_id": job_id},
            },
        )
        res_pat = backend.apply_ops([OperationGroup(document=str(target), operations=(op_pat,))])
        assert res_pat.outcomes[0].error is None

        meas = cast(dict[str, Any], backend.measure_part(str(target)))
        # Expected volume: (100 * 60 - 4 * pi * 5^2) * 10 mm3 = (6000 - 100 * pi) * 10 mm3
        expected_vol = (100.0 * 60.0 - 4.0 * math.pi * 25.0) * 10.0 * 1e-9
        assert meas["volume_m3"] == pytest.approx(expected_vol, rel=1e-3)
    finally:
        backend.close()
        _close_in_solidworks_by_path(target)


def test_live_circular_pattern_flange(tmp_path: Path) -> None:
    """Verify circular pattern feature end-to-end against live SOLIDWORKS."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "round_flange_pattern_holes.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": REFERENCE_ANSWERS["round_flange_pattern_holes"], "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_live_direct_circular_pattern_ops(tmp_path: Path) -> None:
    """Verify direct IPC feature.create with circular_pattern."""
    session = _get_live_session()
    template = _resolve_template()
    target = tmp_path / "direct_cirpattern.SLDPRT"
    job_id = f"live_cirpattern_{time.time_ns()}"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))
    try:
        op_create = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": template, "_meta": {"job_id": job_id}},
        )
        res_create = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_create,))]
        )
        assert res_create.outcomes[0].error is None

        op_sk_base = Operation(
            operation_id=f"{job_id}:2",
            op="sketch.create",
            params={
                "node_id": "sk_base",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "circle",
                        "center": [0.0, 0.0],
                        "diameter": 100.0,
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_base = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_base,))]
        )
        assert res_sk_base.outcomes[0].error is None
        base_sk_id = str(cast(dict[str, Any], res_sk_base.outcomes[0].result)["feature_id"])

        op_ext = Operation(
            operation_id=f"{job_id}:3",
            op="feature.create",
            params={
                "node_id": "ext_base",
                "type": "extrude",
                "profile": base_sk_id,
                "end_condition": {"type": "blind", "depth": 12.0},
                "_meta": {"job_id": job_id},
            },
        )
        res_ext = backend.apply_ops([OperationGroup(document=str(target), operations=(op_ext,))])
        assert res_ext.outcomes[0].error is None

        op_sk_hole = Operation(
            operation_id=f"{job_id}:4",
            op="sketch.create",
            params={
                "node_id": "sk_hole",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "circle",
                        "center": [0.0, 35.0],
                        "diameter": 8.0,
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_hole = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_hole,))]
        )
        assert res_sk_hole.outcomes[0].error is None
        hole_sk_id = str(cast(dict[str, Any], res_sk_hole.outcomes[0].result)["feature_id"])

        op_cut = Operation(
            operation_id=f"{job_id}:5",
            op="feature.create",
            params={
                "node_id": "cut_hole",
                "type": "cut_extrude",
                "profile": hole_sk_id,
                "end_condition": {"type": "through_all_both"},
                "_meta": {"job_id": job_id},
            },
        )
        res_cut = backend.apply_ops([OperationGroup(document=str(target), operations=(op_cut,))])
        assert res_cut.outcomes[0].error is None
        cut_id = str(cast(dict[str, Any], res_cut.outcomes[0].result)["feature_id"])

        op_pat = Operation(
            operation_id=f"{job_id}:6",
            op="feature.create",
            params={
                "node_id": "pat_holes",
                "type": "circular_pattern",
                "seeds": [cut_id],
                "axis": "plane:front",
                "count": 6,
                "spacing": 360.0,
                "equal_spacing": True,
                "_meta": {"job_id": job_id},
            },
        )
        res_pat = backend.apply_ops([OperationGroup(document=str(target), operations=(op_pat,))])
        assert res_pat.outcomes[0].error is None

        meas = cast(dict[str, Any], backend.measure_part(str(target)))
        # Expected volume: (pi * 50^2 - 6 * pi * 4^2) * 12 mm3
        expected_vol = (math.pi * 2500.0 - 6.0 * math.pi * 16.0) * 12.0 * 1e-9
        assert meas["volume_m3"] == pytest.approx(expected_vol, rel=1e-3)
    finally:
        backend.close()
        _close_in_solidworks_by_path(target)


def test_live_mirror_plate(tmp_path: Path) -> None:
    """Verify mirror feature end-to-end against live SOLIDWORKS."""
    session = _get_live_session()
    template = _resolve_template()
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_mirror_hole.SLDPRT"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    service = _start_core(
        tmp_path, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = _call_ok(
            service,
            "apply_part_graph",
            {"graph": REFERENCE_ANSWERS["plate_mirror_hole"], "target_path": str(target)},
        )
        final = _wait_for_job(service, str(applied["execution_id"]))
        assert final["state"] == "COMMITTED", final
        assert target.is_file()

        part_result = cast(dict[str, Any], final["part_result"])
        checks = cast(list[dict[str, Any]], part_result["checks"])
        assert len(checks) > 0
        assert all(c["status"] == "passed" for c in checks), checks
    finally:
        service.stop()
        _close_in_solidworks_by_path(target)


def test_live_direct_mirror_ops(tmp_path: Path) -> None:
    """Verify direct IPC feature.create with mirror."""
    session = _get_live_session()
    template = _resolve_template()
    target = tmp_path / "direct_mirror.SLDPRT"
    job_id = f"live_mirror_{time.time_ns()}"

    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = cast(IpcBackend, provider.acquire(on_notification=lambda _m, _p: None))
    try:
        op_create = Operation(
            operation_id=f"{job_id}:1",
            op="part.create",
            params={"template": template, "_meta": {"job_id": job_id}},
        )
        res_create = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_create,))]
        )
        assert res_create.outcomes[0].error is None

        op_sk_base = Operation(
            operation_id=f"{job_id}:2",
            op="sketch.create",
            params={
                "node_id": "sk_base",
                "plane": "plane:front",
                "entities": [
                    {"type": "line", "start": [-50.0, -25.0], "end": [50.0, -25.0]},
                    {"type": "line", "start": [50.0, -25.0], "end": [50.0, 25.0]},
                    {"type": "line", "start": [50.0, 25.0], "end": [-50.0, 25.0]},
                    {"type": "line", "start": [-50.0, 25.0], "end": [-50.0, -25.0]},
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_base = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_base,))]
        )
        assert res_sk_base.outcomes[0].error is None
        base_sk_id = str(cast(dict[str, Any], res_sk_base.outcomes[0].result)["feature_id"])

        op_ext = Operation(
            operation_id=f"{job_id}:3",
            op="feature.create",
            params={
                "node_id": "ext_base",
                "type": "extrude",
                "profile": base_sk_id,
                "end_condition": {"type": "blind", "depth": 10.0},
                "_meta": {"job_id": job_id},
            },
        )
        res_ext = backend.apply_ops([OperationGroup(document=str(target), operations=(op_ext,))])
        assert res_ext.outcomes[0].error is None

        op_sk_hole = Operation(
            operation_id=f"{job_id}:4",
            op="sketch.create",
            params={
                "node_id": "sk_hole",
                "plane": "plane:front",
                "entities": [
                    {
                        "type": "circle",
                        "center": [25.0, 0.0],
                        "diameter": 10.0,
                    }
                ],
                "_meta": {"job_id": job_id},
            },
        )
        res_sk_hole = backend.apply_ops(
            [OperationGroup(document=str(target), operations=(op_sk_hole,))]
        )
        assert res_sk_hole.outcomes[0].error is None
        hole_sk_id = str(cast(dict[str, Any], res_sk_hole.outcomes[0].result)["feature_id"])

        op_cut = Operation(
            operation_id=f"{job_id}:5",
            op="feature.create",
            params={
                "node_id": "cut_hole",
                "type": "cut_extrude",
                "profile": hole_sk_id,
                "end_condition": {"type": "through_all_both"},
                "_meta": {"job_id": job_id},
            },
        )
        res_cut = backend.apply_ops([OperationGroup(document=str(target), operations=(op_cut,))])
        assert res_cut.outcomes[0].error is None
        cut_id = str(cast(dict[str, Any], res_cut.outcomes[0].result)["feature_id"])

        op_mir = Operation(
            operation_id=f"{job_id}:6",
            op="feature.create",
            params={
                "node_id": "mir_hole",
                "type": "mirror",
                "seeds": [cut_id],
                "plane": "plane:right",
                "merge": True,
                "_meta": {"job_id": job_id},
            },
        )
        res_mir = backend.apply_ops([OperationGroup(document=str(target), operations=(op_mir,))])
        assert res_mir.outcomes[0].error is None

        meas = cast(dict[str, Any], backend.measure_part(str(target)))
        # Expected volume: (100 * 50 * 10 - 2 * pi * 5^2 * 10) mm3 = (50000 - 500 * pi) mm3
        expected_vol = (50000.0 - 500.0 * math.pi) * 1e-9
        assert meas["volume_m3"] == pytest.approx(expected_vol, rel=1e-3)
    finally:
        backend.close()
        _close_in_solidworks_by_path(target)
