"""A14 (threading under real load) and immediate reconnect, through the live named pipe.

Part Chain MVP design sections 7 and 13. Uses only `session.ping`, `document.open` and
`document.close`, and only on a scratch part the spike creates in %TEMP%\\sw-mcp-spike\\.

Owner gate: an interactive SOLIDWORKS 2025+ with the sw-mcp add-in loaded and registered.
The scratch part and the "keep SOLIDWORKS busy" helper come from the PartChainSpike console
project (build it first: `dotnet build -c Release` in tests/live/spikes/PartChainSpike).
"""

import contextlib
import itertools
import os
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from cad_ir.generated.ipc import Operation, OperationGroup
from cad_protocol.backend import IpcBackend
from core_service.discovery import (
    NamedPipeBackendProvider,
    discover_sessions,
    get_default_session_dir,
)

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Windows only"),
    pytest.mark.live,
]

REPO_ROOT = Path(__file__).resolve().parents[2]
SPIKE_EXE = (
    REPO_ROOT
    / "tests"
    / "live"
    / "spikes"
    / "PartChainSpike"
    / "bin"
    / "Release"
    / "net48"
    / "PartChainSpike.exe"
)
WORK_DIR = Path(os.environ.get("TEMP", ".")) / "sw-mcp-spike"
SCRATCH = WORK_DIR / "a14_scratch.SLDPRT"

QUICK_COMMANDS = 1000
OPEN_CLOSE_CYCLES = 20
RECONNECT_CYCLES = 10
BUSY_SECONDS = 14
# A ceiling for one command, not a target.
MAX_SINGLE_COMMAND_S = 30.0

_job_counter = itertools.count(1)


def _op_id() -> str:
    return f"job_live_a14_{next(_job_counter):011d}:1"


def _acquire() -> IpcBackend:
    if not discover_sessions(get_default_session_dir()):
        pytest.skip("No live SOLIDWORKS session with the sw-mcp add-in registered.")
    backend = NamedPipeBackendProvider().acquire(on_notification=lambda _m, _p: None)
    assert isinstance(backend, IpcBackend)
    return backend


def _ping(backend: IpcBackend) -> None:
    backend._client.ping()  # pyright: ignore[reportPrivateUsage]


def _open(backend: IpcBackend) -> None:
    op = Operation(
        operation_id=_op_id(),
        op="document.open",
        params={"path": str(SCRATCH), "read_only": True},
    )
    backend.apply_ops([OperationGroup(document=str(SCRATCH), operations=(op,))])


def _close(backend: IpcBackend) -> None:
    op = Operation(
        operation_id=_op_id(), op="document.close", params={"path": str(SCRATCH), "save": False}
    )
    backend.apply_ops([OperationGroup(document=str(SCRATCH), operations=(op,))])


def _timed(fn: Callable[[], object]) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


@pytest.fixture(scope="module")
def scratch_part() -> Path:
    """The scratch part, made by the spike (the add-in cannot make a .SLDPRT)."""
    if not SCRATCH.exists():
        if not SPIKE_EXE.exists():
            pytest.skip(f"Build the spike first; missing {SPIKE_EXE}")
        result = subprocess.run(
            [str(SPIKE_EXE), "scratch"], capture_output=True, text=True, timeout=120, check=False
        )
        if result.returncode != 0 or not SCRATCH.exists():
            pytest.skip(f"Could not create the scratch part: {result.stdout} {result.stderr}")
    return SCRATCH


@pytest.fixture
def backend(scratch_part: Path) -> Iterator[IpcBackend]:
    assert scratch_part.exists()
    backend = _acquire()
    try:
        yield backend
    finally:
        # Never leave the scratch part open in the engineer's SOLIDWORKS.
        with contextlib.suppress(Exception):
            _close(backend)
        with contextlib.suppress(Exception):
            backend.close()


def test_a14_under_load(backend: IpcBackend) -> None:
    """1,000 quick commands, then open/close cycles: none lost, none stalled."""
    latencies: list[float] = [_timed(lambda: _ping(backend)) for _ in range(QUICK_COMMANDS)]
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]
    print(
        f"\nA14 pings: n={len(latencies)} median={statistics.median(latencies) * 1000:.2f}ms "
        f"p99={p99 * 1000:.2f}ms max={max(latencies) * 1000:.2f}ms"
    )
    assert len(latencies) == QUICK_COMMANDS
    assert max(latencies) < MAX_SINGLE_COMMAND_S

    cycle_times: list[float] = []
    for _ in range(OPEN_CLOSE_CYCLES):
        cycle_times.append(_timed(lambda: _open(backend)))
        cycle_times.append(_timed(lambda: _close(backend)))
        _ping(backend)
    print(f"A14 open/close: {len(cycle_times)} commands, max={max(cycle_times) * 1000:.0f}ms")
    assert max(cycle_times) < MAX_SINGLE_COMMAND_S
    assert backend.completed_operations() is not None


def test_a14_command_while_solidworks_is_busy(backend: IpcBackend) -> None:
    """One command sent while SOLIDWORKS is held busy by rebuilds: it must finish, not drop."""
    if not SPIKE_EXE.exists():
        pytest.skip(f"Build the spike first; missing {SPIKE_EXE}")
    busy = subprocess.Popen(
        [str(SPIKE_EXE), "busy", str(BUSY_SECONDS)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert busy.stdout is not None
        deadline = time.monotonic() + 60
        for line in busy.stdout:
            if "rebuilding for" in line or time.monotonic() > deadline:
                break
        time.sleep(1.0)
        assert busy.poll() is None, "the busy helper ended before the command was sent"
        t_ping = _timed(lambda: _ping(backend))
        t_open = _timed(lambda: _open(backend))
        t_close = _timed(lambda: _close(backend))
        still_busy = busy.poll() is None
        print(
            f"\nA14 busy: ping={t_ping * 1000:.0f}ms open={t_open * 1000:.0f}ms "
            f"close={t_close * 1000:.0f}ms helper still busy afterwards={still_busy}"
        )
        assert max(t_ping, t_open, t_close) < MAX_SINGLE_COMMAND_S
    finally:
        with contextlib.suppress(Exception):
            busy.wait(timeout=60)
        if busy.poll() is None:
            busy.terminate()


def test_reconnect_immediately(scratch_part: Path) -> None:
    """After a close, a new connection is accepted at once and serves commands."""
    assert scratch_part.exists()
    for i in range(RECONNECT_CYCLES):
        first = _acquire()
        try:
            _open(first)
            _close(first)
        finally:
            first.close()
        started = time.perf_counter()
        second = _acquire()  # immediately, no wait
        try:
            _ping(second)
            elapsed = time.perf_counter() - started
            print(f"\nreconnect {i}: acquire+ping {elapsed * 1000:.0f}ms")
        finally:
            with contextlib.suppress(Exception):
                _close(second)
            second.close()
