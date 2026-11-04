"""The job engine: queue, positions, long-poll, cancel and restart recovery (spec 8.4, ADR-053)."""

import threading
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from cad_application.jobs.model import JobView, UnknownJobError
from cad_application.store.job_records import JobRecord
from cad_application.store.journal_records import OpResultRecord, StateRecord
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import FakeBackend, make_hello
from cad_application.testing.job_rig import DRAWING, Rig, make_rig
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import Operation, OperationGroup

GUARD_S = 5.0
LONG_WAIT_MS = 20_000
LONG_WAIT_S = 20.0
THREE = 3
TWO = 2

type Doc = dict[str, JsonValue]


class RealWaitClock(FakeClock):
    """Waits on the condition for real, so a second thread can wake it (guard timeout only)."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()

    def wait(self, cond: threading.Condition, timeout_s: float) -> None:
        self.entered.set()
        cond.wait(min(timeout_s, GUARD_S))


class ScriptedClock(FakeClock):
    """Runs one scripted step while the waiter has released the lock; time never moves."""

    def __init__(self, steps: list[Callable[[], None]]) -> None:
        super().__init__()
        self.steps = steps
        self.waits = 0

    def wait(self, cond: threading.Condition, timeout_s: float) -> None:
        self.waits += 1
        if not self.steps:
            self.advance(timeout_s)
            return
        step = self.steps.pop(0)
        cond.release()
        try:
            step()
        finally:
            cond.acquire()


class Crash(BaseException):
    pass


def _states(rig: Rig, job_id: str) -> list[str]:
    return [r.to for r in rig.journal(job_id) if isinstance(r, StateRecord)]


def _error_code(record: JobRecord) -> object:
    return None if record.error is None else record.error["code"]


def test_queued_position_counts_running_and_earlier(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    first, second, third = rig.submit(), rig.submit(), rig.submit()
    assert [first.queued_position, second.queued_position, third.queued_position] == [0, 1, 2]
    seen: list[tuple[int | None, int | None]] = []

    def before(name: str) -> None:
        if name == "apply_ops" and not seen:
            b, c = rig.engine.status(second.job_id), rig.engine.status(third.job_id)
            assert b is not None
            assert c is not None
            seen.append((b.queued_position, c.queued_position))

    rig.backend.before = before
    assert rig.engine.run_next()
    assert seen == [(1, 2)]
    after = rig.engine.status(second.job_id)
    assert after is not None
    assert after.queued_position == 0
    done = rig.engine.status(first.job_id)
    assert done is not None
    assert done.queued_position is None


def test_jobs_run_in_submission_order(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    ids = [rig.submit().job_id for _ in range(THREE)]
    while rig.engine.run_next():
        pass
    reads = [c.meta.job_id for c in rig.backend.calls if c.name == "snapshot_drawing" and c.meta]
    assert reads == ids
    assert not rig.engine.run_next()


def test_wait_returns_on_state_change(good_snapshot: Doc) -> None:
    clock = RealWaitClock()
    rig = make_rig(snapshot=good_snapshot, clock=clock)
    job = rig.submit()
    got: list[tuple[JobView, bool]] = []
    waiter = threading.Thread(
        target=lambda: got.append(rig.engine.wait_for_change(job.job_id, 5000))
    )
    waiter.start()
    assert clock.entered.wait(GUARD_S)
    rig.engine.cancel(job.job_id)
    waiter.join(GUARD_S)
    assert not waiter.is_alive()
    view, changed = got[0]
    assert (view.state, changed) == ("ABORTED", True)


def test_wait_ignores_progress(good_snapshot: Doc) -> None:
    """EXECUTING step 1 -> step 2 is a progress-only change: the long-poll keeps waiting."""
    gate, in_open = threading.Event(), threading.Event()
    snapshot_gate = threading.Event()
    clock = ScriptedClock([])
    rig = make_rig(snapshot=good_snapshot, block=snapshot_gate, clock=clock)
    job = rig.submit()

    def hold_open(name: str) -> None:
        if name == "apply_ops" and not in_open.is_set():
            in_open.set()
            gate.wait(GUARD_S)

    rig.backend.before = hold_open
    worker = threading.Thread(target=rig.engine.run_next)
    worker.start()
    assert in_open.wait(GUARD_S)
    seen: list[str] = []

    def progress_only() -> None:
        gate.set()  # the open completes: progress 1 -> 2, state stays EXECUTING
        assert rig.backend.snapshot_started.wait(GUARD_S)
        view = rig.engine.status(job.job_id)
        assert view is not None
        seen.append(view.state)

    def finish() -> None:
        snapshot_gate.set()
        worker.join(GUARD_S)

    clock.steps.extend([progress_only, finish])
    view, changed = rig.engine.wait_for_change(job.job_id, LONG_WAIT_MS)
    assert seen == ["EXECUTING"]
    assert clock.waits == TWO  # the progress change did not end the first wait
    assert (view.state, changed) == ("COMMITTED", True)


def test_wait_final_returns_at_once(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()
    assert rig.engine.run_next()
    before = rig.clock.monotonic_s()
    view, changed = rig.engine.wait_for_change(job.job_id, LONG_WAIT_MS)
    assert (view.state, changed) == ("COMMITTED", False)
    assert rig.clock.monotonic_s() == before


def test_wait_expires_without_real_time() -> None:
    rig = make_rig()
    job = rig.submit()
    view, changed = rig.engine.wait_for_change(job.job_id, LONG_WAIT_MS)
    assert (view.state, changed) == ("PLANNED", False)
    assert rig.clock.monotonic_s() >= LONG_WAIT_S


def test_wait_unknown_job_raises() -> None:
    with pytest.raises(UnknownJobError):
        make_rig().engine.wait_for_change("job_00000000000000000000000009", 0)


def test_cancel_planned_aborts_at_once() -> None:
    rig = make_rig()
    job = rig.submit()
    view = rig.engine.cancel(job.job_id)
    assert view.state == "ABORTED"
    assert view.queued_position is None
    assert _error_code(rig.job(job.job_id)) == "EXEC_CANCELLED"
    assert _states(rig, job.job_id) == ["PLANNED", "ABORTED"]
    assert not rig.engine.run_next()
    assert rig.backend.calls == []


def test_cancel_finished_is_no_op(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()
    assert rig.engine.run_next()
    lines = rig.journal(job.job_id)
    assert rig.engine.cancel(job.job_id).state == "COMMITTED"
    assert rig.journal(job.job_id) == lines
    assert not rig.backend.cancel_called


class _ProbeBackend(FakeBackend):
    """Asks, from another thread, whether the engine lock is free while ``cancel`` runs."""

    def __init__(self, block: threading.Event) -> None:
        super().__init__(make_hello(), block=block)
        self.probe: Callable[[], object] = lambda: None
        self.lock_checks: list[bool] = []

    def cancel(self, *, meta: object = None) -> bool:
        asker = threading.Thread(target=self.probe)
        asker.start()
        asker.join(GUARD_S)
        self.lock_checks.append(not asker.is_alive())
        return super().cancel()


def test_cancel_running_calls_backend_outside_lock(good_snapshot: Doc) -> None:
    block = threading.Event()
    probe = _ProbeBackend(block)
    rig = make_rig(snapshot=good_snapshot, backend=probe)
    job = rig.submit()
    probe.probe = lambda: rig.engine.status(job.job_id)
    worker = threading.Thread(target=rig.engine.run_next)
    worker.start()
    assert probe.snapshot_started.wait(GUARD_S)
    rig.engine.cancel(job.job_id)
    worker.join(GUARD_S)
    assert not worker.is_alive()
    assert probe.lock_checks == [True]  # asked on every cancel() call, each time free
    record = rig.job(job.job_id)
    assert (record.state, _error_code(record)) == ("ABORTED", "EXEC_CANCELLED")
    closes = [c for c in probe.calls if c.name == "apply_ops"]
    assert len(closes) == TWO  # the open, then the close of the drawing the job owns


def test_cancel_unknown_job_raises() -> None:
    with pytest.raises(UnknownJobError):
        make_rig().engine.cancel("job_00000000000000000000000009")


def test_status_unknown_is_none() -> None:
    assert make_rig().engine.status("job_00000000000000000000000009") is None


def test_unexpected_error_fails_the_job_in_a_final_state(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()

    def explode(name: str) -> None:
        raise RuntimeError(name)

    rig.backend.before = explode
    assert rig.engine.run_next()
    record = rig.job(job.job_id)
    assert (record.state, _error_code(record)) == ("FAILED", "EXEC_INTERRUPTED")
    assert any(e.event == "job.error" for e in rig.log.events)


def test_restart_recovers_and_status_reads_the_store() -> None:
    rig = make_rig()
    queued = rig.submit()
    rig.stores.close_all()
    restarted = make_rig(fs=rig.fs, clock=FakeClock(datetime(2026, 11, 5, tzinfo=UTC)))
    results = restarted.engine.recover_all()
    assert [j.job_id for r in results for j in r.interrupted] == [queued.job_id]
    view = restarted.engine.status(queued.job_id)
    assert view is not None
    assert view.state == "ABORTED"
    assert _error_code(view.record) == "EXEC_INTERRUPTED"
    assert restarted.engine.wait_for_change(queued.job_id, LONG_WAIT_MS) == (view, False)


def test_reconcile_records_completed_operations_once(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()

    def crash(name: str) -> None:
        raise Crash(name)

    rig.backend.before = crash
    with pytest.raises(Crash):
        rig.engine.run_next()
    rig.stores.close_all()
    restarted = make_rig(fs=rig.fs)
    restarted.engine.recover_all()
    op_id = f"{job.job_id}:1"
    group = OperationGroup(
        document=DRAWING, operations=(Operation(operation_id=op_id, op="document.open", params={}),)
    )
    restarted.backend.apply_ops((group,))  # the add-in completed it before the crash
    assert restarted.engine.reconcile(restarted.backend) == (op_id,)
    assert restarted.engine.reconcile(restarted.backend) == ()
    recovered = [
        r for r in restarted.journal(job.job_id) if isinstance(r, OpResultRecord) and r.recovered
    ]
    assert [r.operation_id for r in recovered] == [op_id]
