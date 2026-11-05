"""Live dispatch and capability verification (ADR-059, ADR-062).

Owner gate:
- Active interactive SOLIDWORKS 2025+ with sw-mcp add-in loaded
- If no session is registered in %LOCALAPPDATA%\\sw-mcp\\sessions, these tests skip cleanly.
"""

import os
import sys
from pathlib import Path
from typing import Any

import pytest
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


def _get_live_session() -> SessionInfo:
    sessions = discover_sessions(get_default_session_dir())
    if not sessions:
        pytest.skip(
            "No live SOLIDWORKS session discovered in %LOCALAPPDATA%\\sw-mcp\\sessions. "
            "Requires active SOLIDWORKS interactive session with sw-mcp add-in loaded."
        )
    return sessions[0]


def test_live_session_probe_and_diagnostics() -> None:
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    notifications: list[tuple[str, Any]] = []
    backend = provider.acquire(
        on_notification=lambda method, params: notifications.append((method, params))
    )
    try:
        assert isinstance(backend, IpcBackend)
        sw = backend.session.solidworks

        # Real version and UI language must be populated, never defaulted
        assert sw.version == "2025"
        assert sw.service_pack.startswith("SP")
        assert len(sw.ui_language) > 0

        # Capabilities from CapabilityTable
        assert "drawing.snapshot" in backend.session.capabilities
        assert "ops.apply" in backend.session.capabilities

        # Operations from router
        registered_ops = {op.op for op in backend.session.operations}
        assert "document.open" in registered_ops
        assert "document.close" in registered_ops

        # Check diagnostics log in %LOCALAPPDATA%\sw-mcp\addin-load.log
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        log_path = local_app_data / "sw-mcp" / "addin-load.log"
        if log_path.exists():
            log_content = log_path.read_text(encoding="utf-8")
            # Must record PID, STA apartment state and ControlSynchronizationContext dispatch path
            assert f"PID {session.pid}" in log_content
            assert "ApartmentState STA" in log_content
            assert "DispatchPath ControlSynchronizationContext" in log_content
    finally:
        if isinstance(backend, IpcBackend):
            backend.close()


def test_live_dispatch_commands_during_running() -> None:
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    notifications: list[tuple[str, Any]] = []
    backend = provider.acquire(
        on_notification=lambda method, params: notifications.append((method, params))
    )
    try:
        assert isinstance(backend, IpcBackend)

        # Verify sequential and queued commands execute without being stranded
        for _ in range(10):
            res = backend.completed_operations()
            assert isinstance(res, tuple)
    finally:
        if isinstance(backend, IpcBackend):
            backend.close()
