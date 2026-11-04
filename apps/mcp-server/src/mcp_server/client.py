import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, cast

if sys.platform == "win32":
    import _winapi  # type: ignore[import-not-found]
else:
    _winapi = None


def _get_default_core_session_file() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
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
    ) -> None:
        if sys.platform != "win32" or _winapi is None:
            raise NotImplementedError("CorePipeClient is only supported on Windows.")

        self._session_file = (
            Path(session_file) if session_file is not None else _get_default_core_session_file()
        )
        self._pipe_name = pipe_name
        self._token = token
        self._handle: int | None = None
        self._next_id = 1

    def connect(self, timeout_s: float = 5.0) -> None:
        assert _winapi is not None
        if not self._pipe_name or not self._token:
            if not self._session_file.exists():
                raise ConnectionError(f"Core session file {self._session_file} does not exist.")
            data = json.loads(self._session_file.read_text(encoding="utf-8"))
            self._pipe_name = data["pipe"]
            self._token = data["token"]

        full_path = (
            self._pipe_name if self._pipe_name.startswith(r"\\") else rf"\\.\pipe\{self._pipe_name}"
        )

        deadline = time.monotonic() + timeout_s
        handle = None
        while time.monotonic() < deadline:
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
                time.sleep(0.05)

        if handle is None:
            raise ConnectionError(f"Failed to connect to core pipe {full_path}")

        self._handle = int(handle)

        hello_req = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": "session.hello",
            "params": {"token": self._token, "protocol": "0.1"},
        }
        res = self._send_request(hello_req)
        if "error" in res:
            self.close()
            raise ConnectionError(f"Handshake rejected: {res['error']}")

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
        if self._handle is None:
            raise ConnectionError("Not connected")

        payload = json.dumps(req).encode("utf-8")
        frame = len(payload).to_bytes(4, "little") + payload
        _winapi.WriteFile(self._handle, frame)

        header = self._read_exact(4)
        length = int.from_bytes(header, "little")
        body = self._read_exact(length)
        return json.loads(body.decode("utf-8"))

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
