"""Core service named pipe host (ADR-041, 12.3, 13.1)."""

import contextlib
import ctypes
import hmac
import json
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Final, cast

from cad_application.tools.registry import UnknownTool
from cad_protocol.framing import MAX_FRAME_BYTES, encode_frame

from core_service.service import CoreService

if sys.platform == "win32":
    import _winapi  # type: ignore[import-not-found]
else:
    _winapi = None

_TOKEN_QUERY: Final = 0x0008
_TOKEN_USER_CLASS: Final = 1
_SDDL_REVISION_1: Final = 1
_PIPE_ACCESS_DUPLEX: Final = 0x00000003
_INVALID_HANDLE_VALUE: Final = ctypes.c_void_p(-1).value


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


def _current_user_sid() -> str:
    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL

    tok = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(tok)):
        raise OSError("OpenProcessToken failed")
    try:
        needed = wintypes.DWORD(0)
        advapi32.GetTokenInformation(tok, _TOKEN_USER_CLASS, None, 0, ctypes.byref(needed))
        buf = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            tok, _TOKEN_USER_CLASS, buf, needed, ctypes.byref(needed)
        ):
            raise OSError("GetTokenInformation failed")
        sid_ptr = ctypes.cast(buf, ctypes.POINTER(wintypes.LPVOID)).contents
        advapi32.ConvertSidToStringSidW.argtypes = [
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
        sid_str = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid_ptr, ctypes.byref(sid_str)):
            raise OSError("ConvertSidToStringSidW failed")
        try:
            assert sid_str.value is not None
            return str(sid_str.value)
        finally:
            kernel32.LocalFree(sid_str)
    finally:
        kernel32.CloseHandle(tok)


def _create_user_only_pipe(full_path: str, sddl: str) -> int:
    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.ULONG),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL

    p_sd = wintypes.LPVOID()
    sd_size = wintypes.ULONG(0)
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, _SDDL_REVISION_1, ctypes.byref(p_sd), ctypes.byref(sd_size)
    ):
        raise OSError("ConvertStringSecurityDescriptorToSecurityDescriptorW failed")
    try:
        sa = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), p_sd, 0)
        kernel32.CreateNamedPipeW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_SecurityAttributes),
        ]
        kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
        handle = kernel32.CreateNamedPipeW(
            full_path,
            _PIPE_ACCESS_DUPLEX,
            0,
            255,
            65536,
            65536,
            0,
            ctypes.byref(sa),
        )
        if handle is None or handle == _INVALID_HANDLE_VALUE:
            raise OSError("CreateNamedPipeW failed")
        return int(handle)
    finally:
        kernel32.LocalFree(p_sd)


def _get_default_core_session_file() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "sw-mcp" / "core.json"
    return Path.home() / "AppData" / "Local" / "sw-mcp" / "core.json"


class PipeHost:
    """Listens on \\\\.\\pipe\\sw-mcp-core-<id> and dispatches tool requests to CoreService."""

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
        user_sid = _current_user_sid()
        self._sddl = f"D:P(A;;GA;;;{user_sid})"
        self._stopping = threading.Event()
        self._shutdown_requested = threading.Event()
        self._started = threading.Event()
        self._server_thread: threading.Thread | None = None
        self._handles: list[int] = []
        self._lock = threading.Lock()

    @property
    def shutdown_requested(self) -> threading.Event:
        return self._shutdown_requested

    def start(self) -> None:
        self._server_thread = threading.Thread(
            target=self._listen_loop,
            name="core-pipe-host",
            daemon=True,
        )
        self._server_thread.start()
        self._started.wait(timeout=5.0)

        self._session_file.parent.mkdir(parents=True, exist_ok=True)
        session_data = {
            "pipe_name": self._pipe_name,
            "pipe": self._pipe_name,
            "token": self._token,
            "pid": os.getpid(),
            "protocol": "0.1",
            "version": "0.1.0",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        tmp_file = self._session_file.with_suffix(".json.tmp")
        tmp_file.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
        tmp_file.replace(self._session_file)

    def stop(self) -> None:
        self._stopping.set()
        self._shutdown_requested.set()
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
                handle = _create_user_only_pipe(self._full_path, self._sddl)
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

    def _is_tool_enabled(self, toolset: str) -> bool:
        enabled = set(self._service.settings.toolsets)
        return "full" in enabled or toolset in enabled

    def _call_tool_request(self, req_id: object, params: dict[str, Any]) -> dict[str, object]:
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if not isinstance(tool_name, str) or tool_name not in self._service.registry.names:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"Unknown tool: {tool_name!r}"},
            }
        contract = self._service.registry.contract(tool_name)
        if not self._is_tool_enabled(contract.toolset):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": (
                        f"Tool {tool_name!r} is disabled "
                        f"(toolset {contract.toolset!r} is not enabled)"
                    ),
                },
            }
        try:
            result = self._service.call_tool(tool_name, tool_args)
        except UnknownTool as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"Unknown tool: {exc}"},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error ({type(exc).__name__})",
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "summary": result.summary,
                "envelope": result.envelope,
            },
        }

    def _handle_request(
        self, method: str, req_id: object, params: dict[str, Any]
    ) -> dict[str, object]:
        if method == "session.ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"pong": True}}
        if method in ("session.shutdown", "core.shutdown"):
            self._shutdown_requested.set()
            return {"jsonrpc": "2.0", "id": req_id, "result": {"stopping": True}}
        if method == "tools/list":
            tools: list[dict[str, object]] = []
            for name in self._service.registry.names:
                contract = self._service.registry.contract(name)
                if not self._is_tool_enabled(contract.toolset):
                    continue
                tools.append(dict(contract.tool_definition()))
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
        if method == "tools/call":
            return self._call_tool_request(req_id, params)
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
                    provided_token = params_dict.get("token")
                    if (
                        method == "session.hello"
                        and isinstance(provided_token, str)
                        and hmac.compare_digest(
                            provided_token.encode("utf-8"), self._token.encode("utf-8")
                        )
                    ):
                        authenticated = True
                        res = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {"protocol": "0.1", "version": "0.1.0"},
                        }
                        _winapi.WriteFile(handle, encode_frame(json.dumps(res).encode("utf-8")))
                    else:
                        with contextlib.suppress(Exception):
                            ctypes.windll.kernel32.DisconnectNamedPipe(wintypes.HANDLE(handle))
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
