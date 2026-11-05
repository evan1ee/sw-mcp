"""Contract tests for MCP tools/list and toolset filtering (spec 12.3, 12.4.1, 13.3.3)."""

import json
import sys
import time
from pathlib import Path
from typing import Any, cast

import anyio
import pytest
from cad_application.tools.contracts import load_contracts
from core_service.providers import ReplayBackendProvider
from core_service.server.pipe_host import PipeHost
from core_service.service import CoreService
from core_service.testing import ServiceRig
from mcp import ClientSession, MCPError, types
from mcp_server.client import CorePipeClient, CorePipeError
from mcp_server.server import create_mcp_server

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows named pipes only")

ROOT = Path(__file__).resolve().parents[2]
INSTALL_ROOT = str(ROOT)
SCHEMAS_MCP = ROOT / "schemas" / "mcp"
IPC = ROOT / "tests" / "fixtures" / "ipc"


def _start_stack(
    tmp_path: Path,
    *,
    sub: str = "default",
    extra_env: dict[str, str] | None = None,
) -> tuple[CoreService, PipeHost, str, str, str]:
    base = tmp_path / sub
    base.mkdir(parents=True, exist_ok=True)
    _project, drawing = ServiceRig.prepare(base)
    env = ServiceRig.environment(base)
    if extra_env:
        env.update(extra_env)
    provider = ReplayBackendProvider.from_file(str(IPC / "check_drawing_borrowed.jsonl"))
    service = CoreService.start(
        install_root=INSTALL_ROOT,
        environ=env,
        provider=provider,
    )
    assert isinstance(service, CoreService), service
    pipe_name = f"test-sw-mcp-list-{sub}-{int(time.time() * 1000)}"
    token = f"token-{sub}"
    session_file = base / "local" / "sw-mcp" / "core.json"
    host = PipeHost(service, pipe_name=pipe_name, token=token, session_file=session_file)
    host.start()
    return service, host, pipe_name, token, drawing


async def _mcp_list_tools(pipe_name: str, token: str) -> list[types.Tool]:
    client = CorePipeClient(pipe_name=pipe_name, token=token)
    client.connect()
    server = create_mcp_server(client)
    s2c_send, s2c_recv = anyio.create_memory_object_stream[Any](10)
    c2s_send, c2s_recv = anyio.create_memory_object_stream[Any](10)
    out: list[types.Tool] = []
    try:
        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    server.run,
                    c2s_recv,
                    s2c_send,
                    server.create_initialization_options(),
                )
                async with ClientSession(s2c_recv, c2s_send) as session:
                    await session.initialize()
                    res = await session.list_tools()
                    out = list(res.tools)
                tg.cancel_scope.cancel()
        except BaseExceptionGroup as eg:
            raise _unwrap_exception_group(eg) from None
        return out
    finally:
        client.close()


def _unwrap_exception_group(exc: BaseException) -> BaseException:
    cur: BaseException = exc
    while isinstance(cur, BaseExceptionGroup):
        sub = cast("tuple[BaseException, ...]", cur.exceptions)
        if len(sub) != 1:
            break
        cur = sub[0]
    return cast("BaseException", cur)


async def _mcp_call_tool(
    pipe_name: str, token: str, name: str, arguments: dict[str, Any]
) -> types.CallToolResult:
    client = CorePipeClient(pipe_name=pipe_name, token=token)
    client.connect()
    server = create_mcp_server(client)
    s2c_send, s2c_recv = anyio.create_memory_object_stream[Any](10)
    c2s_send, c2s_recv = anyio.create_memory_object_stream[Any](10)
    out: types.CallToolResult | None = None
    try:
        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    server.run,
                    c2s_recv,
                    s2c_send,
                    server.create_initialization_options(),
                )
                async with ClientSession(s2c_recv, c2s_send) as session:
                    await session.initialize()
                    out = await session.call_tool(name, arguments)
                tg.cancel_scope.cancel()
        except BaseExceptionGroup as eg:
            raise _unwrap_exception_group(eg) from None
        assert out is not None
        return out
    finally:
        client.close()


def test_list_matches_contracts(tmp_path: Path) -> None:
    contracts = load_contracts()
    service, host, pipe_name, token, _drawing = _start_stack(
        tmp_path,
        sub="all",
        extra_env={"SWMCP_MCP__TOOLSETS": '["core", "drawing"]'},
    )
    try:
        tools = anyio.run(_mcp_list_tools, pipe_name, token)
        by_name = {t.name: t for t in tools}
        expected_names = {name for name, c in contracts.items() if c.toolset in {"core", "drawing"}}
        assert set(by_name) == expected_names

        for name, tool in by_name.items():
            raw = json.loads((SCHEMAS_MCP / f"{name}.json").read_text(encoding="utf-8"))
            contract = contracts[name]
            assert tool.description == raw["description"]
            assert tool.input_schema == raw["input"]
            assert tool.output_schema is not None
            assert tool.output_schema.get("type") == "object"
            assert tool.output_schema == contract.output_schema
            assert tool.annotations is not None
            dumped_annotations = tool.annotations.model_dump(by_alias=True, exclude_none=True)
            assert set(dumped_annotations) == {
                "readOnlyHint",
                "destructiveHint",
                "idempotentHint",
                "openWorldHint",
            }
            assert dumped_annotations == contract.annotations()
    finally:
        host.stop()
        service.stop()


def test_default_hides_drawing_tools(tmp_path: Path) -> None:
    service_def, host_def, pipe_def, token_def, _ = _start_stack(tmp_path, sub="def")
    try:
        default_tools = anyio.run(_mcp_list_tools, pipe_def, token_def)
        default_names = {t.name for t in default_tools}
        assert "check_drawing" not in default_names
        assert "get_drawing_report" not in default_names
        assert {
            "apply_part_graph",
            "validate_part_graph",
            "list_feature_types",
            "get_feature_schema",
            "get_execution_status",
            "cancel_execution",
        } <= default_names
    finally:
        host_def.stop()
        service_def.stop()

    service_drw, host_drw, pipe_drw, token_drw, _ = _start_stack(
        tmp_path,
        sub="drw",
        extra_env={"SWMCP_MCP__TOOLSETS": '["core", "drawing"]'},
    )
    try:
        drawing_tools = anyio.run(_mcp_list_tools, pipe_drw, token_drw)
        drawing_names = {t.name for t in drawing_tools}
        assert "check_drawing" in drawing_names
        assert "get_drawing_report" in drawing_names
    finally:
        host_drw.stop()
        service_drw.stop()


def test_disabled_tool_refused(tmp_path: Path) -> None:
    service, host, pipe_name, token, drawing = _start_stack(tmp_path, sub="refused")
    try:
        client = CorePipeClient(pipe_name=pipe_name, token=token)
        client.connect()
        try:
            with pytest.raises(CorePipeError) as exc_info:
                client.call_tool("check_drawing", {"path": drawing})
            assert exc_info.value.code == -32602  # noqa: PLR2004
        finally:
            client.close()

        with pytest.raises(MCPError) as mcp_exc:
            anyio.run(_mcp_call_tool, pipe_name, token, "check_drawing", {"path": drawing})
        assert mcp_exc.value.error.code == -32602  # noqa: PLR2004

        in_process = service.call_tool("check_drawing", {"path": drawing})
        assert isinstance(in_process.envelope, dict)
        assert in_process.envelope.get("ok") is True
    finally:
        host.stop()
        service.stop()
