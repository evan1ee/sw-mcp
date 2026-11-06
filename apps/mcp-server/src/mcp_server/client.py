"""Named-pipe client connecting the MCP front-end to the per-user core service (ADR-041, 13.2.1)."""

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

if sys.platform == "win32":
    import _winapi  # type: ignore[import-not-found]
else:
    _winapi = None


class CorePipeError(Exception):
    """JSON-RPC protocol error returned over the core service pipe."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _get_default_core_session_file(environ: Mapping[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "sw-mcp" / "core.json"
    return Path.home() / "AppData" / "Local" / "sw-mcp" / "core.json"


class CorePipeClient:
    """Connects to the core service over a Windows named pipe with 4-byte framing."""

    def __init__(
        self,
        *,
        pipe_name: str | None = None,
        token: str | None = None,
        session_file: Path | str | None = None,
        env: Mapping[str, str] | None = None,
        auto_start: bool | None = None,
    ) -> None:
        if sys.platform != "win32" or _winapi is None:
            raise NotImplementedError("CorePipeClient is only supported on Windows.")

        self._env = dict(env) if env is not None else dict(os.environ)
        self._session_file = (
            Path(session_file)
            if session_file is not None
            else _get_default_core_session_file(self._env)
        )
        self._pipe_name = pipe_name
        self._token = token
        # Explicit pipe and token are pinned; otherwise rediscover through the session file,
        # since a restarted core issues a new pipe and token.
        self._pinned = pipe_name is not None and token is not None
        self._auto_start = (
            (pipe_name is None and token is None) if auto_start is None else auto_start
        )
        self._handle: int | None = None
        self._next_id = 1
        self._lock = threading.RLock()

    def _read_session_file(self) -> tuple[str, str] | None:
        if not self._session_file.is_file():
            return None
        try:
            data: object = json.loads(self._session_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        doc = cast(dict[str, Any], data)
        pipe = doc.get("pipe_name") or doc.get("pipe")
        tok = doc.get("token")
        if isinstance(pipe, str) and pipe and isinstance(tok, str) and tok:
            return pipe, tok
        return None

    def _try_open_and_handshake(self, pipe_name: str, token: str, wait_s: float) -> bool:
        assert _winapi is not None
        full_path = pipe_name if pipe_name.startswith(r"\\") else rf"\\.\pipe\{pipe_name}"
        deadline = time.monotonic() + max(wait_s, 0.05)
        handle = None
        while True:
            try:
                handle = _winapi.CreateFile(
                    full_path,
                    _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
                    0,
                    0,
                    _winapi.OPEN_EXISTING,
                    0,
                    0,
                )
                break
            except OSError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)

        self._handle = int(handle)
        hello_req = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": "session.hello",
            "params": {"token": token, "protocol": "0.1"},
        }
        try:
            res = self._send_request(hello_req)
        except (ConnectionError, CorePipeError, EOFError, OSError):
            self.close()
            return False
        if "error" in res:
            self.close()
            return False
        self._pipe_name = pipe_name
        self._token = token
        return True

    def _spawn_core_process(self) -> None:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
        subprocess.Popen(
            [sys.executable, "-m", "core_service"],
            env=self._env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

    def connect(self, timeout_s: float = 10.0) -> None:
        if self._pinned and self._pipe_name and self._token:
            if not self._try_open_and_handshake(self._pipe_name, self._token, timeout_s):
                raise ConnectionError(f"Failed to connect to core pipe {self._pipe_name}")
            return

        info = self._read_session_file()
        if info is not None and self._try_open_and_handshake(info[0], info[1], 0.5):
            return

        if not self._auto_start:
            raise ConnectionError(
                f"Core service is not running (session file {self._session_file})."
            )

        self._spawn_core_process()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            info = self._read_session_file()
            if info is not None and self._try_open_and_handshake(info[0], info[1], 0.2):
                return
            time.sleep(0.05)

        raise ConnectionError(f"Timed out waiting for core service at {self._session_file}.")

    def list_tools(self) -> list[dict[str, Any]]:
        req: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": "tools/list",
            "params": {},
        }
        res = self._send_request(req)
        result = res.get("result")
        if not isinstance(result, dict):
            return []
        tools_dict = cast(dict[str, Any], result)
        tools = tools_dict.get("tools")
        if not isinstance(tools, list):
            return []
        return cast(list[dict[str, Any]], tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        req: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        res = self._send_request(req)
        result = res.get("result")
        if not isinstance(result, dict):
            return {}
        return cast(dict[str, Any], result)

    def close(self) -> None:
        assert _winapi is not None
        if self._handle is not None:
            with contextlib.suppress(Exception):
                _winapi.CloseHandle(self._handle)
            self._handle = None

    def _alloc_id(self) -> int:
        cur = self._next_id
        self._next_id += 1
        return cur

    def _send_request(self, req: dict[str, Any]) -> dict[str, Any]:
        assert _winapi is not None
        with self._lock:
            if self._handle is None:
                # A dropped connection is re-established before the next request. A request
                # that failed mid-flight is never resent: the caller sees the error.
                self.connect()
            handle = self._handle
            if handle is None:
                raise ConnectionError("Not connected")

            payload = json.dumps(req).encode("utf-8")
            frame = len(payload).to_bytes(4, "little") + payload
            try:
                _winapi.WriteFile(handle, frame)
                header = self._read_exact(4)
                length = int.from_bytes(header, "little")
                body = self._read_exact(length)
            except (EOFError, OSError) as exc:
                self.close()
                raise ConnectionError("Core pipe disconnected") from exc

            parsed: object = json.loads(body.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ConnectionError("Invalid JSON-RPC response from core pipe")
            res = cast(dict[str, Any], parsed)
            err = res.get("error")
            if isinstance(err, dict):
                err_dict = cast(dict[str, Any], err)
                raise CorePipeError(
                    int(err_dict.get("code", -32603)),
                    str(err_dict.get("message", "Core pipe error")),
                    err_dict.get("data"),
                )
            return res

    def _read_exact(self, n: int) -> bytes:
        assert _winapi is not None
        if self._handle is None:
            raise ConnectionError("Not connected")
        buf = bytearray()
        while len(buf) < n:
            chunk, _ = _winapi.ReadFile(self._handle, n - len(buf))
            if not chunk:
                raise EOFError("Core pipe disconnected")
            buf.extend(chunk)
        return bytes(buf)
