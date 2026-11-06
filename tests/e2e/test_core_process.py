"""End-to-end process tests for sw-mcp-core and sw-mcp-mcp (ADR-041, 13.1, 13.2.1)."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

import pytest
from core_service.testing import ServiceRig
from mcp_server.client import CorePipeClient

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows named pipes only")

ROOT = Path(__file__).resolve().parents[2]
IPC = ROOT / "tests" / "fixtures" / "ipc"
REPLAY_FILE = str(IPC / "check_drawing_borrowed.jsonl")


def _wait_for_file(path: Path, timeout_s: float = 10.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                raw = path.read_text(encoding="utf-8")
                data: object = json.loads(raw)
                if isinstance(data, dict):
                    doc = cast("dict[str, object]", data)
                    if "pipe_name" in doc and "token" in doc:
                        return doc
            except (OSError, ValueError):
                pass
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {path}")


def _env_for(tmp_path: Path) -> tuple[dict[str, str], Path]:
    ServiceRig.prepare(tmp_path)
    rig_env = ServiceRig.environment(tmp_path)
    env = {
        **os.environ,
        **rig_env,
        "CORE_SERVICE_REPLAY_FIXTURE": REPLAY_FILE,
    }
    session_file = Path(rig_env["LOCALAPPDATA"]) / "sw-mcp" / "core.json"
    return env, session_file


def test_core_start_stop(tmp_path: Path) -> None:
    env, session_file = _env_for(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-m", "core_service", "--replay", REPLAY_FILE],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        info = _wait_for_file(session_file)
        assert isinstance(info.get("pid"), int)
        assert session_file.is_file()

        client = CorePipeClient(env=env, auto_start=False)
        client.connect()
        try:
            res = client.call_tool("list_feature_types", {})
            assert isinstance(res, dict)
            envelope_raw = res.get("envelope", res)
            assert isinstance(envelope_raw, dict)
            envelope = cast("dict[str, object]", envelope_raw)
            assert envelope.get("ok") is True
        finally:
            client.close()

        stop_res = subprocess.run(
            [sys.executable, "-m", "core_service", "stop"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert stop_res.returncode == 0, stop_res.stderr
        rc = proc.wait(timeout=10)
        assert rc == 0
        assert not session_file.exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_second_core_refused(tmp_path: Path) -> None:
    env, session_file = _env_for(tmp_path)
    first = subprocess.Popen(
        [sys.executable, "-m", "core_service", "--replay", REPLAY_FILE],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        info = _wait_for_file(session_file)
        first_pid = info.get("pid")
        assert isinstance(first_pid, int)

        second = subprocess.run(
            [sys.executable, "-m", "core_service", "--replay", REPLAY_FILE],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert second.returncode != 0
        assert first.poll() is None
        assert session_file.is_file()
        assert _wait_for_file(session_file).get("pid") == first_pid
    finally:
        subprocess.run(
            [sys.executable, "-m", "core_service", "stop"],
            env=env,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if first.poll() is None:
            try:
                first.wait(timeout=5)
            except subprocess.TimeoutExpired:
                first.kill()
                first.wait(timeout=5)


def test_front_end_starts_core(tmp_path: Path) -> None:
    env, session_file = _env_for(tmp_path)
    assert not session_file.exists()

    client = CorePipeClient(env=env, auto_start=True)
    try:
        client.connect()
        assert session_file.is_file()
        res = client.call_tool("list_feature_types", {})
        assert isinstance(res, dict)
        envelope_raw = res.get("envelope", res)
        assert isinstance(envelope_raw, dict)
        envelope = cast("dict[str, object]", envelope_raw)
        assert envelope.get("ok") is True
    finally:
        client.close()
        subprocess.run(
            [sys.executable, "-m", "core_service", "stop"],
            env=env,
            capture_output=True,
            timeout=10,
            check=False,
        )
    deadline = time.monotonic() + 5.0
    while session_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not session_file.exists()
