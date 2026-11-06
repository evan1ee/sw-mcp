"""Tests for the core named-pipe host and MCP SDK front-end (ADR-034, ADR-041, ADR-044, 12.3)."""

import ctypes
import os
import sys
import time
from pathlib import Path
from typing import Any, cast

import anyio
import pytest
from core_service.providers import ReplayBackendProvider
from core_service.server.pipe_host import PipeHost
from core_service.service import CoreService
from core_service.testing import ServiceRig
from mcp import ClientSession, MCPError, types
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp_server.client import CorePipeClient, CorePipeError
from mcp_server.server import create_mcp_server

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows named pipes only")

INSTALL_ROOT = str(Path(__file__).parents[3])
IPC = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ipc"


@pytest.fixture
def running_service_and_host(tmp_path: Path):
    pipe_name = f"test-sw-mcp-core-{int(time.time() * 1000)}"
    token = "test-core-token-abc"

    project, drawing = ServiceRig.prepare(tmp_path)
    provider = ReplayBackendProvider.from_file(str(IPC / "check_drawing_borrowed.jsonl"))
    env = ServiceRig.environment(tmp_path)
    service = CoreService.start(
        install_root=INSTALL_ROOT,
        environ=env,
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
        yield service, host, pipe_name, token, drawing, project, env
    finally:
        host.stop()
        service.stop()


def _unwrap_exception_group(exc: BaseException) -> BaseException:
    cur: BaseException = exc
    while isinstance(cur, BaseExceptionGroup):
        sub = cast("tuple[BaseException, ...]", cur.exceptions)
        if len(sub) != 1:
            break
        cur = sub[0]
    return cast("BaseException", cur)


async def _with_mcp_session(pipe_name: str, token: str, fn: Any) -> Any:
    client = CorePipeClient(pipe_name=pipe_name, token=token)
    client.connect()
    server = create_mcp_server(client)
    s2c_send, s2c_recv = anyio.create_memory_object_stream[Any](10)
    c2s_send, c2s_recv = anyio.create_memory_object_stream[Any](10)
    out: Any = None
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
                    out = await fn(session)
                tg.cancel_scope.cancel()
        except BaseExceptionGroup as eg:
            raise _unwrap_exception_group(eg) from None
        return out
    finally:
        client.close()


def test_call_maps_result(running_service_and_host: Any) -> None:
    _, _, pipe_name, token, _, _, _ = running_service_and_host

    async def _run(session: ClientSession) -> tuple[types.CallToolResult, types.CallToolResult]:
        ok_res = await session.call_tool("list_feature_types", {})
        fail_res = await session.call_tool(
            "get_execution_status",
            {"execution_id": "job_01000000000000000000000000"},
        )
        return ok_res, fail_res

    ok_res, fail_res = anyio.run(_with_mcp_session, pipe_name, token, _run)

    ok_wire = ok_res.model_dump(by_alias=True, exclude_none=True)
    assert ok_res.is_error is False
    assert len(ok_res.content) == 1
    assert isinstance(ok_res.content[0], types.TextContent)
    assert ok_res.content[0].text
    assert not ok_res.content[0].text.lstrip().startswith("{")
    ok_sc: object = ok_res.structured_content
    assert isinstance(ok_sc, dict)
    ok_struct = cast("dict[str, Any]", ok_sc)
    assert ok_struct.get("ok") is True
    assert isinstance(ok_struct.get("data"), dict)
    assert ok_wire.get("structuredContent") == ok_struct

    fail_wire = fail_res.model_dump(by_alias=True, exclude_none=True)
    assert fail_res.is_error is True
    assert fail_wire.get("isError") is True
    assert len(fail_res.content) == 1
    assert isinstance(fail_res.content[0], types.TextContent)
    assert fail_res.content[0].text
    fail_sc: object = fail_res.structured_content
    assert isinstance(fail_sc, dict)
    fail_struct = cast("dict[str, Any]", fail_sc)
    assert fail_struct.get("ok") is False
    assert fail_wire.get("structuredContent") == fail_struct
    err_obj = fail_struct.get("error")
    assert isinstance(err_obj, dict)
    err_dict = cast("dict[str, Any]", err_obj)
    assert err_dict.get("code") == "EXEC_NOT_FOUND"


def test_unknown_tool_protocol_error(running_service_and_host: Any) -> None:
    _, _, pipe_name, token, _, _, _ = running_service_and_host

    async def _run(session: ClientSession) -> None:
        await session.call_tool("unknown_tool_xyz", {})

    with pytest.raises(MCPError) as exc_info:
        anyio.run(_with_mcp_session, pipe_name, token, _run)
    assert exc_info.value.error.code == -32602  # noqa: PLR2004


def test_bad_token_closed(running_service_and_host: Any) -> None:
    _, _, pipe_name, token, _, _, _ = running_service_and_host

    bad_client = CorePipeClient(pipe_name=pipe_name, token="wrong-secret-token", auto_start=False)
    try:
        with pytest.raises((ConnectionError, OSError, CorePipeError)):
            bad_client.connect()
    finally:
        bad_client.close()

    good_client = CorePipeClient(pipe_name=pipe_name, token=token, auto_start=False)
    good_client.connect()
    try:
        tools = good_client.list_tools()
        assert len(tools) > 0
    finally:
        good_client.close()


def test_stdio_utf8(running_service_and_host: Any) -> None:
    _, _, _, _, _, _, rig_env = running_service_and_host
    kernel32 = ctypes.windll.kernel32
    orig_in_cp = kernel32.GetConsoleCP()
    orig_out_cp = kernel32.GetConsoleOutputCP()

    chinese_key = "草图_法兰盘_测试件"
    child_env = {
        **os.environ,
        **rig_env,
        "PYTHONIOENCODING": "cp936",
    }

    async def _run_stdio() -> types.CallToolResult:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server"],
            env=child_env,
        )
        async with (
            stdio_client(params) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            return await session.call_tool(
                "validate_part_graph",
                {
                    "graph": {
                        "module": "part",
                        "id": "plate_4h",
                        "schema_version": "0.1",
                        "units": "mm",
                        "origin": "built",
                        "nodes": {
                            chinese_key: {
                                "type": "sketch",
                                "plane": "plane:front",
                                "entities": {},
                            }
                        },
                    }
                },
            )

    try:
        kernel32.SetConsoleCP(936)
        kernel32.SetConsoleOutputCP(936)
        res = anyio.run(_run_stdio)
    finally:
        if orig_in_cp:
            kernel32.SetConsoleCP(orig_in_cp)
        if orig_out_cp:
            kernel32.SetConsoleOutputCP(orig_out_cp)

    assert res.is_error is True
    res_sc: object = res.structured_content
    assert isinstance(res_sc, dict)
    res_struct = cast("dict[str, Any]", res_sc)
    assert res_struct.get("ok") is False
    serialized = str(res_struct)
    assert chinese_key in serialized
