"""Core service named pipe host (ADR-041)."""

import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

from cad_ir.generated.schemas import SCHEMAS
from cad_protocol.framing import MAX_FRAME_BYTES, encode_frame

from core_service.service import CoreService

if sys.platform == "win32":
    import _winapi  # type: ignore[import-not-found]
else:
    _winapi = None


def _get_default_core_session_file() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "sw-mcp" / "core.json"
    return Path.home() / "AppData" / "Local" / "sw-mcp" / "core.json"


class PipeHost:
    """Listens on \\.\\pipe\\sw-mcp-core-<id> and dispatches tool requests to CoreService."""

    def __init__(
        self,
        service: CoreService,
        *,
        pipe_name: str | None = None,
        token: str | None = None,
        session_file: Path | str | None = None,
    ) -> None:
        if sys.platform != "win32" or _winapi is None:
            raise NotImplementedError("PipeHost is only supported on Windows.")

        self._service = service
        self._pipe_name = pipe_name or f"sw-mcp-core-{os.getpid()}"
        self._full_path = (
            self._pipe_name if self._pipe_name.startswith(r"\\") else rf"\\.\pipe\{self._pipe_name}"
        )
        self._token = token or f"core-tok-{os.urandom(16).hex()}"
        self._session_file = (
            Path(session_file) if session_file is not None else _get_default_core_session_file()
        )
        self._stopping = threading.Event()
        self._started = threading.Event()
        self._server_thread: threading.Thread | None = None
        self._handles: list[int] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self._session_file.parent.mkdir(parents=True, exist_ok=True)
        session_data = {
            "pipe": self._pipe_name,
            "token": self._token,
            "protocol": "0.1",
            "version": "0.1.0",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._session_file.write_text(json.dumps(session_data, indent=2), encoding="utf-8")

        self._server_thread = threading.Thread(
            target=self._listen_loop,
            name="core-pipe-host",
            daemon=True,
        )
        self._server_thread.start()
        self._started.wait(timeout=5.0)

    def stop(self) -> None:
        self._stopping.set()
        with contextlib.suppress(Exception):
            self._session_file.unlink(missing_ok=True)

        with contextlib.suppress(Exception):
            dummy = _winapi.CreateFile(  # type: ignore[attr-defined]
                self._full_path,
                _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,  # type: ignore[attr-defined]
                0,
                0,
                _winapi.OPEN_EXISTING,  # type: ignore[attr-defined]
                0,
                0,
            )
            _winapi.CloseHandle(dummy)  # type: ignore[attr-defined]

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=2.0)

        with self._lock:
            for handle in self._handles:
                with contextlib.suppress(Exception):
                    _winapi.CloseHandle(handle)  # type: ignore[attr-defined]
            self._handles.clear()

    def _listen_loop(self) -> None:
        assert _winapi is not None
        while not self._stopping.is_set():
            try:
                handle = _winapi.CreateNamedPipe(
                    self._full_path,
                    _winapi.PIPE_ACCESS_DUPLEX,
                    0,
                    255,
                    65536,
                    65536,
                    0,
                    0,
                )
            except Exception:
                break

            with self._lock:
                self._handles.append(int(handle))
            self._started.set()

            try:
                _winapi.ConnectNamedPipe(handle, False)
            except Exception:
                if self._stopping.is_set():
                    with contextlib.suppress(Exception):
                        _winapi.CloseHandle(handle)
                    break

            if self._stopping.is_set():
                with contextlib.suppress(Exception):
                    _winapi.CloseHandle(handle)
                break

            worker = threading.Thread(
                target=self._client_worker,
                args=(int(handle),),
                name="core-client-worker",
                daemon=True,
            )
            worker.start()

    def _read_exact(self, handle: int, n: int) -> bytes:
        assert _winapi is not None
        buf = bytearray()
        while len(buf) < n:
            chunk, _ = _winapi.ReadFile(handle, n - len(buf))
            if not chunk:
                raise EOFError("pipe closed")
            buf.extend(chunk)
        return bytes(buf)

    def _handle_request(
        self, method: str, req_id: object, params: dict[str, Any]
    ) -> dict[str, object]:
        if method == "session.ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"pong": True}}
        if method == "tools/list":
            tools: list[dict[str, object]] = []
            for name in self._service.registry.names:
                contract = self._service.registry.contract(name)
                schema_data = SCHEMAS.get(contract.schema_id)
                input_schema: object = (
                    schema_data.get("input", {}) if isinstance(schema_data, dict) else {}
                )
                tools.append(
                    {
                        "name": name,
                        "description": contract.description,
                        "inputSchema": input_schema,
                    }
                )
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result = self._service.call_tool(tool_name, tool_args)
            return {"jsonrpc": "2.0", "id": req_id, "result": result.envelope}
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method {method} not found"},
        }

    def _client_worker(self, handle: int) -> None:
        assert _winapi is not None
        authenticated = False
        try:
            while not self._stopping.is_set():
                try:
                    header = self._read_exact(handle, 4)
                    length = int.from_bytes(header, "little")
                    if length > MAX_FRAME_BYTES:
                        break
                    body = self._read_exact(handle, length)
                    req_obj: object = json.loads(body.decode("utf-8"))
                    if not isinstance(req_obj, dict):
                        break
                    req: dict[str, Any] = cast(dict[str, Any], req_obj)
                except (EOFError, OSError, ValueError):
                    break

                req_id = req.get("id")
                method = str(req.get("method", ""))
                params_obj = req.get("params")
                params_dict: dict[str, Any] = (
                    cast(dict[str, Any], params_obj) if isinstance(params_obj, dict) else {}
                )

                if not authenticated:
                    if method == "session.hello" and params_dict.get("token") == self._token:
                        authenticated = True
                        res = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {"protocol": "0.1", "version": "0.1.0"},
                        }
                        _winapi.WriteFile(handle, encode_frame(json.dumps(res).encode("utf-8")))
                    else:
                        break
                    continue

                res = self._handle_request(method, req_id, params_dict)
                _winapi.WriteFile(handle, encode_frame(json.dumps(res).encode("utf-8")))
        finally:
            with self._lock:
                if handle in self._handles:
                    self._handles.remove(handle)
            with contextlib.suppress(Exception):
                _winapi.CloseHandle(handle)
