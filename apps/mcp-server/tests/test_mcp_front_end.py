"""Tests for the core named-pipe host and MCP front-end (ADR-041)."""

import json
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest
from core_service.providers import ReplayBackendProvider
from core_service.server.pipe_host import PipeHost
from core_service.service import CoreService
from core_service.testing import ServiceRig
from mcp_server.client import CorePipeClient
from mcp_server.server import McpServer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows named pipes only")

INSTALL_ROOT = str(Path(__file__).parents[3])
IPC = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ipc"


@pytest.fixture
def running_service_and_host(tmp_path: Path):
    pipe_name = f"test-sw-mcp-core-{int(time.time() * 1000)}"
    token = "test-core-token-abc"

    project, drawing = ServiceRig.prepare(tmp_path)
    provider = ReplayBackendProvider.from_file(str(IPC / "check_drawing_borrowed.jsonl"))
    service = CoreService.start(
        install_root=INSTALL_ROOT,
        environ=ServiceRig.environment(tmp_path),
        provider=provider,
    )
    assert isinstance(service, CoreService)

    session_file = tmp_path / "local" / "sw-mcp" / "core.json"
    host = PipeHost(
        service,
        pipe_name=pipe_name,
        token=token,
        session_file=session_file,
    )
    host.start()

    try:
        yield service, host, pipe_name, token, drawing, project
    finally:
        host.stop()
        service.stop()


def test_core_pipe_host_receives_tool_call(running_service_and_host: Any) -> None:
    _, _, pipe_name, token, _, _ = running_service_and_host

    client = CorePipeClient(pipe_name=pipe_name, token=token)
    client.connect()
    try:
        envelope = client.call_tool(
            "get_execution_status",
            {"execution_id": "job_01000000000000000000000000"},
        )
        assert isinstance(envelope, dict)
        assert envelope.get("ok") is False
        assert envelope.get("error", {}).get("code") == "EXEC_NOT_FOUND"
    finally:
        client.close()


def test_mcp_front_end_lists_tools(running_service_and_host: Any) -> None:
    _, _, pipe_name, token, _, _ = running_service_and_host

    server = McpServer(pipe_name=pipe_name, token=token)
    server.connect()
    try:
        req: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        res = server.handle_message(req)
        assert res is not None
        assert res.get("id") == 1
        tools = res.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        assert "check_drawing" in tool_names
        assert "get_drawing_report" in tool_names
        assert "get_execution_status" in tool_names
        assert "cancel_execution" in tool_names
    finally:
        server.close()


def test_mcp_front_end_forwards_tool_call(running_service_and_host: Any) -> None:
    _, _, pipe_name, token, drawing, _project = running_service_and_host

    server = McpServer(pipe_name=pipe_name, token=token)
    server.connect()
    call_id = 2
    try:
        req: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": "check_drawing",
                "arguments": {
                    "path": drawing,
                },
            },
        }
        res = server.handle_message(req)
        assert res is not None
        assert res.get("id") == call_id
        content = res.get("result", {}).get("content", [])
        assert len(content) > 0
        envelope_obj: object = json.loads(content[0]["text"])
        assert isinstance(envelope_obj, dict)
        envelope = cast(dict[str, Any], envelope_obj)
        assert envelope.get("ok") is True
        data = envelope.get("data")
        assert isinstance(data, dict)
        assert "execution_id" in data
    finally:
        server.close()
