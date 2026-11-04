"""Live smoke verification against a running SOLIDWORKS session (ADR-039, Section 15.2).

Owner gate:
- HKCU add-in registration for `sw-mcp.AddIn.dll`
- Interactive desktop session with SOLIDWORKS 2025+ visible
If no session is registered in %LOCALAPPDATA%\\sw-mcp\\sessions, these tests skip cleanly.
"""

import os
import sys
from pathlib import Path
from typing import Any

import pytest
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated.ipc import Operation, OperationGroup
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

SNAPSHOT_SCHEMA_URI = "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"


def _get_live_session() -> SessionInfo:
    sessions = discover_sessions(get_default_session_dir())
    if not sessions:
        pytest.skip(
            "No live SOLIDWORKS session discovered in %LOCALAPPDATA%\\sw-mcp\\sessions. "
            "Requires active SOLIDWORKS interactive session with sw-mcp add-in loaded."
        )
    return sessions[0]


def test_live_session_discovery() -> None:
    session = _get_live_session()
    assert session.pid > 0
    assert session.pipe.startswith(r"\\.\pipe\sw-mcp-") or session.pipe.startswith("sw-mcp-")
    assert len(session.token) > 0


def test_live_session_handshake() -> None:
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))

    notifications: list[tuple[str, Any]] = []
    backend = provider.acquire(
        on_notification=lambda method, params: notifications.append((method, params))
    )
    assert backend is not None
    assert backend.session.protocol == "0.1"


def test_live_drawing_snapshot() -> None:
    test_drawing = os.environ.get("SW_MCP_TEST_DRAWING")
    if not test_drawing or not Path(test_drawing).exists():
        pytest.skip(
            "SW_MCP_TEST_DRAWING environment variable not set or file does not exist. "
            "Set SW_MCP_TEST_DRAWING to a scratch copy of a .slddrw to test snapshot extraction."
        )

    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = provider.acquire(on_notification=lambda _m, _p: None)

    open_op = Operation(
        operation_id="job_live_test_00000000001:1",
        op="document.open",
        params={"path": test_drawing, "read_only": True, "fully_resolved": True},
    )
    close_op = Operation(
        operation_id="job_live_test_00000000001:2",
        op="document.close",
        params={"path": test_drawing, "save": False},
    )

    try:
        backend.apply_ops([OperationGroup(document=test_drawing, operations=(open_op,))])
        snapshot = backend.snapshot_drawing(document=test_drawing)
        assert snapshot is not None
        assert isinstance(snapshot, dict)

        issues = validate_against_schema(snapshot, SNAPSHOT_SCHEMA_URI)
        assert issues == ()
    finally:
        backend.apply_ops([OperationGroup(document=test_drawing, operations=(close_op,))])
