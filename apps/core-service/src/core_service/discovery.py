"""Session discovery for SOLIDWORKS add-in instances (spec 8.6.1)."""

import contextlib
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

if sys.platform == "win32":
    import ctypes
else:
    ctypes = None  # type: ignore[assignment]

from cad_application.ports import Backend, BackendUnavailable
from cad_ir.core.json_types import JsonValue
from cad_protocol.backend import IpcBackend
from cad_protocol.client.ipc_client import IpcClient
from cad_protocol.client.pipe_transport import NamedPipeTransport
from cad_protocol.client.transport import TransportClosed
from cad_protocol.errors import IpcError

type NotificationCallback = Callable[[str, JsonValue], None]


@dataclass(frozen=True, slots=True)
class SessionInfo:
    pipe: str
    token: str
    pid: int
    solidworks: dict[str, Any]
    addin_version: str
    protocol: str
    started_at: str


def get_default_session_dir(environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "sw-mcp" / "sessions"
    return Path.home() / "AppData" / "Local" / "sw-mcp" / "sessions"


def is_solidworks_running(pid: int) -> bool:
    """Checks whether the process with the given PID is a running SLDWORKS.exe."""
    if sys.platform != "win32" or ctypes is None:
        return False
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_query_limited_info = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_info, False, pid)
        if not handle:
            return False
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                exe_name = Path(buf.value).name.lower()
                return exe_name == "sldworks.exe"
            return False
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


def discover_sessions(
    session_dir: Path,
    is_process_running: Callable[[int], bool] = is_solidworks_running,
) -> list[SessionInfo]:
    """Lists session files, cleans up dead PIDs, and returns live SessionInfo objects."""
    if not session_dir.exists():
        return []

    sessions: list[SessionInfo] = []
    for path in session_dir.glob("*.json"):
        pid = 0
        with contextlib.suppress(ValueError):
            pid = int(path.stem)
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, dict):
                path.unlink(missing_ok=True)
                continue
            content = cast(dict[str, Any], raw)
            pid_raw = content.get("pid", pid)
            pid = int(cast(int | str, pid_raw))
            if pid <= 0 or not is_process_running(pid):
                path.unlink(missing_ok=True)
                continue

            pipe = str(content.get("pipe", ""))
            token = str(content.get("token", ""))
            sw_info = content.get("solidworks", {})
            addin_ver = str(content.get("addin_version", ""))
            proto = str(content.get("protocol", "0.1"))
            started = str(content.get("started_at", ""))

            sessions.append(
                SessionInfo(
                    pipe=pipe,
                    token=token,
                    pid=pid,
                    solidworks=dict(cast(dict[str, Any], sw_info)),
                    addin_version=addin_ver,
                    protocol=proto,
                    started_at=started,
                )
            )
        except json.JSONDecodeError:
            path.unlink(missing_ok=True)
        except Exception:
            if pid <= 0 or not is_process_running(pid):
                path.unlink(missing_ok=True)

    return sessions


def resolve_session(sessions: list[SessionInfo], target_session: str = "auto") -> SessionInfo:
    """Selects the target session per spec 8.6.1 rules."""
    if target_session == "auto":
        if not sessions:
            raise BackendUnavailable("BACKEND_LOST", "No active SOLIDWORKS session found.")
        if len(sessions) > 1:
            pids = sorted(s.pid for s in sessions)
            pid_vals: list[JsonValue] = [p for p in pids]
            details: dict[str, JsonValue] = {"pids": pid_vals}
            raise BackendUnavailable(
                "BACKEND_SESSION_AMBIGUOUS",
                f"Multiple SOLIDWORKS sessions found: {pids}",
                details,
            )
        return sessions[0]

    try:
        wanted_pid = int(target_session)
    except ValueError:
        raise BackendUnavailable(
            "BACKEND_LOST", f"Invalid session identifier: {target_session}"
        ) from None

    for s in sessions:
        if s.pid == wanted_pid:
            return s

    raise BackendUnavailable("BACKEND_LOST", f"SOLIDWORKS session {wanted_pid} not found.")


class NamedPipeBackendProvider:
    """Backend provider connecting to discovered live SOLIDWORKS add-in pipes."""

    def __init__(
        self,
        *,
        session_dir: Path | str | None = None,
        target_session: str = "auto",
        is_process_running: Callable[[int], bool] | None = None,
    ) -> None:
        self._session_dir = (
            Path(session_dir) if session_dir is not None else get_default_session_dir()
        )
        self._target_session = target_session
        self._is_process_running = (
            is_process_running if is_process_running is not None else is_solidworks_running
        )

    def acquire(self, on_notification: NotificationCallback) -> Backend:
        sessions = discover_sessions(self._session_dir, self._is_process_running)
        selected = resolve_session(sessions, self._target_session)
        try:
            transport = NamedPipeTransport(selected.pipe)
        except (TransportClosed, OSError) as exc:
            raise BackendUnavailable(
                "BACKEND_LOST", f"Could not connect to add-in pipe: {exc}"
            ) from None

        client = IpcClient(
            transport,
            token=selected.token,
            on_notification=on_notification,
            reader_thread=True,
        )
        try:
            return IpcBackend(client)
        except IpcError as error:
            raise BackendUnavailable(error.code, error.message, error.details) from None
