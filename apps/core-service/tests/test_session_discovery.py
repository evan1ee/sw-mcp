"""Tests for session discovery and resolution (spec 8.6.1)."""

import json
from pathlib import Path

import pytest
from cad_application.ports import BackendUnavailable
from core_service.discovery import (
    NamedPipeBackendProvider,
    SessionInfo,
    discover_sessions,
    resolve_session,
)


def _make_session_file(
    folder: Path,
    pid: int,
    pipe: str = "sw-mcp-addin-1-abc",
    token: str = "tok-123",
    version: str = "2025",
) -> Path:
    data = {
        "pipe": pipe,
        "token": token,
        "pid": pid,
        "solidworks": {"version": version, "service_pack": "SP3.0"},
        "addin_version": "0.1.0",
        "protocol": "0.1",
        "started_at": "2026-11-04T10:00:00Z",
    }
    file = folder / f"{pid}.json"
    file.write_text(json.dumps(data), encoding="utf-8")
    return file


PID_1 = 1001
PID_2 = 1002
PID_SINGLE = 123
PID_A = 100
PID_B = 200


def test_discover_sessions_finds_live_sessions(tmp_path: Path) -> None:
    _make_session_file(tmp_path, pid=PID_1)
    _make_session_file(tmp_path, pid=PID_2)

    # Fake process checker: PID_1 is running, PID_2 is dead
    def is_running(pid: int) -> bool:
        return pid == PID_1

    sessions = discover_sessions(tmp_path, is_process_running=is_running)

    assert len(sessions) == 1
    assert sessions[0].pid == PID_1
    assert sessions[0].token == "tok-123"

    # The dead session file should have been deleted
    assert not (tmp_path / f"{PID_2}.json").exists()
    assert (tmp_path / f"{PID_1}.json").exists()


def test_discover_sessions_cleans_corrupt_file(tmp_path: Path) -> None:
    bad_file = tmp_path / "999.json"
    bad_file.write_text("not json at all", encoding="utf-8")

    sessions = discover_sessions(tmp_path, is_process_running=lambda _: True)
    assert sessions == []
    assert not bad_file.exists()


def test_resolve_session_auto_single() -> None:
    session = SessionInfo(
        pipe="pipe-1",
        token="tok-1",
        pid=PID_SINGLE,
        solidworks={},
        addin_version="0.1.0",
        protocol="0.1",
        started_at="",
    )
    res = resolve_session([session], "auto")
    assert res.pid == PID_SINGLE


def test_resolve_session_auto_none_raises_backend_lost() -> None:
    with pytest.raises(BackendUnavailable) as exc:
        resolve_session([], "auto")
    assert exc.value.code == "BACKEND_LOST"


def test_resolve_session_auto_multiple_raises_ambiguous() -> None:
    s1 = SessionInfo("p1", "t1", PID_A, {}, "0.1", "0.1", "")
    s2 = SessionInfo("p2", "t2", PID_B, {}, "0.1", "0.1", "")

    with pytest.raises(BackendUnavailable) as exc:
        resolve_session([s1, s2], "auto")
    assert exc.value.code == "BACKEND_SESSION_AMBIGUOUS"
    assert exc.value.details == {"pids": [PID_A, PID_B]}


def test_resolve_session_explicit_pid() -> None:
    s1 = SessionInfo("p1", "t1", PID_A, {}, "0.1", "0.1", "")
    s2 = SessionInfo("p2", "t2", PID_B, {}, "0.1", "0.1", "")

    res = resolve_session([s1, s2], str(PID_B))
    assert res.pid == PID_B


def test_resolve_session_explicit_pid_missing_raises_backend_lost() -> None:
    s1 = SessionInfo("p1", "t1", PID_A, {}, "0.1", "0.1", "")
    with pytest.raises(BackendUnavailable) as exc:
        resolve_session([s1], "999")
    assert exc.value.code == "BACKEND_LOST"


def test_named_pipe_provider_no_sessions_raises(tmp_path: Path) -> None:
    provider = NamedPipeBackendProvider(session_dir=tmp_path, target_session="auto")
    with pytest.raises(BackendUnavailable) as exc:
        provider.acquire(lambda _m, _p: None)
    assert exc.value.code == "BACKEND_LOST"
