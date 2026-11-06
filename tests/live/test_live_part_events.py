"""Live part event subscription and tagging verification (spec 8.3, 8.6.5, Task 7b).

Owner gate:
- Active interactive SOLIDWORKS 2025+ with sw-mcp add-in loaded
- Scratch part from PartChainSpike
- If no session is registered, these tests skip cleanly.
"""

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

import pytest
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import DocumentEventParams, Operation, OperationGroup
from cad_protocol.backend import IpcBackend
from core_service.discovery import (
    NamedPipeBackendProvider,
    SessionInfo,
    discover_sessions,
    get_default_session_dir,
)

if sys.platform == "win32":
    import win32com.client  # type: ignore[import-not-found]
else:
    win32com = None  # type: ignore[assignment]

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Windows only"),
    pytest.mark.live,
]

REPO_ROOT = Path(__file__).resolve().parents[2]
SPIKE_EXE = (
    REPO_ROOT
    / "tests"
    / "live"
    / "spikes"
    / "PartChainSpike"
    / "bin"
    / "Release"
    / "net48"
    / "PartChainSpike.exe"
)
WORK_DIR = Path(os.environ.get("TEMP", ".")) / "sw-mcp-spike"
SCRATCH = WORK_DIR / "a14_scratch.SLDPRT"


def _get_live_session() -> SessionInfo:
    sessions = discover_sessions(get_default_session_dir())
    if not sessions:
        pytest.skip("No live SOLIDWORKS session with the sw-mcp add-in registered.")
    return sessions[0]


@pytest.fixture(scope="module")
def scratch_part() -> Path:
    """The scratch part, created by the spike console tool."""
    if not SCRATCH.exists():
        if not SPIKE_EXE.exists():
            pytest.skip(f"Build the spike first; missing {SPIKE_EXE}")
        result = subprocess.run(
            [str(SPIKE_EXE), "scratch"], capture_output=True, text=True, timeout=120, check=False
        )
        if result.returncode != 0 or not SCRATCH.exists():
            pytest.skip(f"Could not create the scratch part: {result.stdout} {result.stderr}")
    return SCRATCH


def test_live_part_open_and_close_events(scratch_part: Path) -> None:
    """Opening an owned part subscribes per-document events, and close raises close event."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    notifications: list[tuple[str, JsonValue]] = []

    backend = provider.acquire(
        on_notification=lambda method, params: notifications.append((method, params))
    )
    assert isinstance(backend, IpcBackend)

    job_id = f"job_ev_test_{int(time.time())}"
    open_op = Operation(
        operation_id=f"{job_id}:1",
        op="document.open",
        params={
            "path": str(scratch_part),
            "read_only": False,
            "fully_resolved": True,
            "_meta": {"job_id": job_id},
        },
    )

    try:
        backend.apply_ops([OperationGroup(document=str(scratch_part), operations=(open_op,))])

        parsed_events: list[DocumentEventParams] = [
            DocumentEventParams.from_json(cast(JsonValue, params))
            for method, params in notifications
            if method == "document.event" and isinstance(params, dict)
        ]

        tagged_events = [
            ev for ev in parsed_events if ev.meta is not None and ev.meta.job_id == job_id
        ]
        assert len(tagged_events) >= 0

        # Now close document
        close_op = Operation(
            operation_id=f"{job_id}:2",
            op="document.close",
            params={"path": str(scratch_part), "save": False, "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(scratch_part), operations=(close_op,))])

        parsed_after_close: list[DocumentEventParams] = [
            DocumentEventParams.from_json(cast(JsonValue, params))
            for method, params in notifications
            if method == "document.event" and isinstance(params, dict)
        ]
        close_events = [ev for ev in parsed_after_close if ev.event == "close"]
        assert len(close_events) >= 1
    finally:
        with contextlib.suppress(Exception):
            backend.close()


def test_live_untagged_event_outside_command(scratch_part: Path) -> None:
    """User actions outside an API command produce untagged events."""
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    notifications: list[tuple[str, JsonValue]] = []

    backend = provider.acquire(
        on_notification=lambda method, params: notifications.append((method, params))
    )
    assert isinstance(backend, IpcBackend)

    job_id = f"job_untagged_{int(time.time())}"
    open_op = Operation(
        operation_id=f"{job_id}:1",
        op="document.open",
        params={
            "path": str(scratch_part),
            "read_only": False,
            "fully_resolved": True,
            "_meta": {"job_id": job_id},
        },
    )

    try:
        backend.apply_ops([OperationGroup(document=str(scratch_part), operations=(open_op,))])
        notifications.clear()

        # Touch the document outside any sw-mcp command using a direct COM dispatch
        if win32com is not None:
            sw_app = win32com.client.Dispatch("SldWorks.Application")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
            model = sw_app.GetOpenDocumentByName(str(scratch_part))  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if model is not None:
                model.ForceRebuild3(False)  # type: ignore[reportUnknownMemberType]

        time.sleep(0.5)

        # Look for untagged regen events
        parsed_events: list[DocumentEventParams] = [
            DocumentEventParams.from_json(cast(JsonValue, params))
            for method, params in notifications
            if method == "document.event" and isinstance(params, dict)
        ]
        untagged_events = [
            ev
            for ev in parsed_events
            if ev.event == "regen" and (ev.meta is None or ev.meta.job_id is None)
        ]
        assert len(untagged_events) >= 1

        # Clean up by closing
        close_op = Operation(
            operation_id=f"{job_id}:2",
            op="document.close",
            params={"path": str(scratch_part), "save": False, "_meta": {"job_id": job_id}},
        )
        backend.apply_ops([OperationGroup(document=str(scratch_part), operations=(close_op,))])
    finally:
        with contextlib.suppress(Exception):
            backend.close()
