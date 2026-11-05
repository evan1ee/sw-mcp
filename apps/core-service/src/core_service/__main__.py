"""Entry point for the sw-mcp-core background service (ADR-041, 13.1, 13.2.1)."""

import argparse
import contextlib
import json
import os
import signal
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from cad_application.config.settings import ConfigError
from cad_application.ports import BackendProvider, LockHeld
from cad_protocol.framing import MAX_FRAME_BYTES, encode_frame

from core_service.os_fs import OsFileSystem
from core_service.providers import NamedPipeBackendProvider, ReplayBackendProvider
from core_service.server.pipe_host import PipeHost
from core_service.service import CoreService

if sys.platform == "win32":
    import _winapi  # type: ignore[import-not-found]
else:
    _winapi = None


def _default_install_root() -> str:
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / "standards").is_dir():
        return str(candidate)
    return os.getcwd()


def _local_sw_mcp_dir(environ: dict[str, str]) -> Path:
    local_app_data = environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "sw-mcp"
    return Path.home() / "AppData" / "Local" / "sw-mcp"


def _send_pipe_rpc(handle: int, method: str, params: dict[str, Any], req_id: int) -> dict[str, Any]:
    assert _winapi is not None
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    ).encode("utf-8")
    _winapi.WriteFile(handle, encode_frame(payload))

    def _read_exact(n: int) -> bytes:
        assert _winapi is not None
        buf = bytearray()
        while len(buf) < n:
            chunk, _ = _winapi.ReadFile(handle, n - len(buf))
            if not chunk:
                raise EOFError("pipe closed")
            buf.extend(chunk)
        return bytes(buf)

    header = _read_exact(4)
    length = int.from_bytes(header, "little")
    if length > MAX_FRAME_BYTES:
        raise ValueError("frame too large")
    body = _read_exact(length)
    parsed: object = json.loads(body.decode("utf-8"))
    return cast("dict[str, Any]", parsed) if isinstance(parsed, dict) else {}


def _read_session_endpoint(session_file: Path) -> tuple[str, str] | None:
    try:
        data: object = json.loads(session_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    doc = cast("dict[str, Any]", data)
    pipe_name = doc.get("pipe_name") or doc.get("pipe")
    token = doc.get("token")
    if isinstance(pipe_name, str) and isinstance(token, str):
        return pipe_name, token
    return None


def _stop_running_core(state_dir: Path) -> int:
    if sys.platform != "win32" or _winapi is None:
        return 1
    session_file = state_dir / "core.json"
    if not session_file.is_file():
        return 0
    endpoint = _read_session_endpoint(session_file)
    if endpoint is None:
        return 1
    pipe_name, token = endpoint

    full_path = pipe_name if pipe_name.startswith(r"\\") else rf"\\.\pipe\{pipe_name}"
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
    except OSError:
        with contextlib.suppress(OSError):
            session_file.unlink(missing_ok=True)
        return 0

    try:
        _send_pipe_rpc(handle, "session.hello", {"token": token, "client": "sw-mcp-core-stop"}, 1)
        _send_pipe_rpc(handle, "session.shutdown", {}, 2)
    except (EOFError, OSError, ValueError):
        pass
    finally:
        with contextlib.suppress(Exception):
            _winapi.CloseHandle(handle)

    deadline = time.monotonic() + 5.0
    while session_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    return 0


def run_core(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sw-mcp-core")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=("start", "stop"),
        help="Start or stop the per-user core service.",
    )
    parser.add_argument(
        "--replay",
        dest="replay",
        default=None,
        help="Optional JSONL IPC transcript path for replay testing.",
    )
    parser.add_argument(
        "--install-root",
        dest="install_root",
        default=None,
        help="Installation root directory.",
    )
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])

    environ = dict(os.environ)
    state_dir = _local_sw_mcp_dir(environ)
    if args.command == "stop":
        return _stop_running_core(state_dir)

    fs = OsFileSystem()
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = str(state_dir / "core.lock")
    try:
        lock = fs.lock_exclusive(lock_path)
    except (LockHeld, OSError):
        sys.stderr.write("sw-mcp-core: another core service instance is already running.\n")
        return 1

    try:
        replay_path = args.replay or environ.get("CORE_SERVICE_REPLAY_FIXTURE")
        provider: BackendProvider = (
            ReplayBackendProvider.from_file(replay_path)
            if replay_path
            else NamedPipeBackendProvider()
        )
        install_root = args.install_root or _default_install_root()
        service = CoreService.start(
            install_root=install_root,
            environ=environ,
            provider=provider,
            fs=fs,
        )
        if isinstance(service, ConfigError):
            sys.stderr.write(
                f"sw-mcp-core: configuration error ({service.code}) at {service.origin}: "
                f"{service.message}\n"
            )
            return 1

        session_file = state_dir / "core.json"
        host = PipeHost(service, session_file=session_file)

        def _request_stop(_signum: int, _frame: object) -> None:
            host.shutdown_requested.set()

        signal.signal(signal.SIGINT, _request_stop)
        signal.signal(signal.SIGTERM, _request_stop)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _request_stop)

        host.start()
        try:
            while not host.shutdown_requested.is_set():
                host.shutdown_requested.wait(timeout=0.1)
        finally:
            host.stop()
            service.stop()
    finally:
        lock.release()
    return 0


def main() -> None:
    raise SystemExit(run_core())


if __name__ == "__main__":
    main()
