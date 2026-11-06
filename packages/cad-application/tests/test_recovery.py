"""Crash recovery, spec 13.2.3 Phase 1a."""

import pytest
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord, JobState
from cad_application.store.journal import record_completed_operations, recover, transition
from cad_application.store.journal_records import (
    BatchSentRecord,
    DocumentRecord,
    JournalRecord,
    OpResultRecord,
    StateRecord,
)
from cad_application.testing.builders import STORE_DIR, new_job, open_store
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_ir.core.json_types import JsonValue

TS = "2026-11-04T09:00:00.000Z"
ERROR: dict[str, JsonValue] = {"code": "BACKEND_LOST", "message": "gone", "retryable": "safe"}
PATH_A = "C:\\Work\\a.slddrw"
PATH_B = "C:\\Work\\b.slddrw"
_PATH = ["PLANNED", "VALIDATED", "EXECUTING", "VERIFYING"]


def _job_in(
    store: FileStore, ids: SequentialIdSource, clock: FakeClock, state: JobState
) -> JobRecord:
    """A job driven through the real transitions up to ``state``."""
    job = new_job(ids, clock)
    store.create_job(job)
    if state in _PATH:
        for step in _PATH[1 : _PATH.index(state) + 1]:
            job = transition(store, job, step, "test")  # type: ignore[arg-type]
        return job
    job = transition(store, job, "VALIDATED", "test")
    if state == "COMMITTED":
        job = transition(store, transition(store, job, "EXECUTING", "t"), "VERIFYING", "t")
    return transition(store, job, state, "test", ERROR if state != "COMMITTED" else None)


def _env() -> tuple[FileStore, MemoryFileSystem, FakeClock, SequentialIdSource]:
    fs = MemoryFileSystem()
    clock = FakeClock()
    return open_store(fs, clock), fs, clock, SequentialIdSource()


def _restart(store: FileStore, fs: MemoryFileSystem, clock: FakeClock) -> FileStore:
    fs.drop_locks()  # the old process died
    return open_store(fs, clock)


def _journal(store: FileStore, job_id: str) -> tuple[JournalRecord, ...]:
    journal = store.read_journal(job_id)
    assert not isinstance(journal, StoreError)
    return journal


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("PLANNED", "ABORTED"),
        ("VALIDATED", "FAILED"),
        ("EXECUTING", "FAILED"),
        ("VERIFYING", "FAILED"),
    ],
)
def test_recovery_marks_interrupted(state: JobState, expected: JobState) -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, state)
    reopened = _restart(store, fs, clock)
    result = recover(reopened, clock)
    saved = reopened.get_job(job.job_id)
    assert isinstance(saved, JobRecord)
    assert saved.state == expected
    assert saved.error is not None
    assert saved.error["code"] == "EXEC_INTERRUPTED"
    assert saved.ended_at is not None
    last = _journal(reopened, job.job_id)[-1]
    assert isinstance(last, StateRecord)
    assert (last.to, last.error) == (expected, saved.error)
    assert [j.job_id for j in result.interrupted] == [job.job_id]
    assert recover(reopened, clock).interrupted == ()  # a second run finds nothing to do


@pytest.mark.parametrize("state", ["COMMITTED", "FAILED", "ABORTED"])
def test_final_jobs_untouched_by_recovery(state: JobState) -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, state)
    before_job = store.get_job(job.job_id)
    before_journal = _journal(store, job.job_id)
    reopened = _restart(store, fs, clock)
    result = recover(reopened, clock)
    assert result.interrupted == ()
    assert reopened.get_job(job.job_id) == before_job
    assert _journal(reopened, job.job_id) == before_journal


def test_journal_wins_over_job_json() -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, "EXECUTING")
    # The journal says FAILED (state record written), job.json still says EXECUTING.
    store.append(
        job.job_id,
        StateRecord("2026-11-04T09:05:00.000Z", job.job_id, "EXECUTING", "FAILED", "lost", ERROR),
    )
    assert store.get_job(job.job_id) == job
    reopened = _restart(store, fs, clock)
    result = recover(reopened, clock)
    saved = reopened.get_job(job.job_id)
    assert isinstance(saved, JobRecord)
    assert saved.state == "FAILED"
    assert saved.error == ERROR  # the journal's error, not an invented EXEC_INTERRUPTED
    assert saved.ended_at == "2026-11-04T09:05:00.000Z"
    assert result.reconciled == (job.job_id,)
    assert result.interrupted == ()
    states = [r for r in _journal(reopened, job.job_id) if isinstance(r, StateRecord)]
    assert [r.to for r in states] == ["PLANNED", "VALIDATED", "EXECUTING", "FAILED"]


def test_documents_unknown_after_crash() -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, "EXECUTING")
    store.append(job.job_id, DocumentRecord(TS, job.job_id, PATH_A, "open", True))
    store.append(job.job_id, DocumentRecord(TS, job.job_id, PATH_B, "open", False))
    store.append(job.job_id, DocumentRecord(TS, job.job_id, PATH_A.upper(), "close", True))
    reopened = _restart(store, fs, clock)
    recover(reopened, clock)
    saved = reopened.get_job(job.job_id)
    assert isinstance(saved, JobRecord)
    assert [(d.path, d.owned, d.state) for d in saved.documents] == [(PATH_B, False, "unknown")]


def test_completed_operations_recorded_once() -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, "EXECUTING")
    op1, op2 = f"{job.job_id}:1", f"{job.job_id}:2"
    store.append(job.job_id, BatchSentRecord(TS, job.job_id, 1, (op1, op2), (PATH_A,)))
    store.append(job.job_id, OpResultRecord(TS, job.job_id, op1, True, None))
    reopened = _restart(store, fs, clock)
    result = recover(reopened, clock)
    assert result.pending_operation_ids == {job.job_id: (op2,)}
    recorded = record_completed_operations(reopened, result, [op1, op2, "job_other:1"])
    assert recorded == (op2,)
    again = record_completed_operations(reopened, result, [op1, op2])
    assert again == ()
    results = [r for r in _journal(reopened, job.job_id) if isinstance(r, OpResultRecord)]
    assert [(r.operation_id, r.recovered) for r in results] == [(op1, False), (op2, True)]


def test_pending_operations_only_for_interrupted_jobs() -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, "FAILED")
    store.append(job.job_id, BatchSentRecord(TS, job.job_id, 1, (f"{job.job_id}:1",), ()))
    reopened = _restart(store, fs, clock)
    assert recover(reopened, clock).pending_operation_ids == {}


def test_corrupt_journal_is_reported_and_left_alone() -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, "EXECUTING")
    path = f"{STORE_DIR}\\jobs\\{job.job_id}\\journal.jsonl"
    fs.write_atomic(path, fs.read_bytes(path) + b"garbage\n" + fs.read_bytes(path))
    reopened = _restart(store, fs, clock)
    result = recover(reopened, clock)
    assert result.corrupt == (job.job_id,)
    assert reopened.get_job(job.job_id) == job


def test_job_folder_without_job_json_is_an_orphan() -> None:
    store, fs, clock, ids = _env()
    job = new_job(ids, clock)
    store.create_job(job)
    fs.remove(f"{STORE_DIR}\\jobs\\{job.job_id}\\job.json")
    reopened = _restart(store, fs, clock)
    result = recover(reopened, clock)
    assert result.orphans == (job.job_id,)
    assert result.interrupted == ()


def test_recovery_records_failed_operations() -> None:
    store, fs, clock, ids = _env()
    job = _job_in(store, ids, clock, "EXECUTING")
    op1, op2 = f"{job.job_id}:1", f"{job.job_id}:2"
    store.append(job.job_id, BatchSentRecord(TS, job.job_id, 1, (op1, op2), (PATH_A,)))
    reopened = _restart(store, fs, clock)
    result = recover(reopened, clock)
    assert result.pending_operation_ids == {job.job_id: (op1, op2)}

    # op1 succeeded, op2 failed with applied effect
    completed = [op1]
    failed = [{"operation_id": op2, "code": "BACKEND_REBUILD_ERROR", "effect": "applied"}]
    recorded = record_completed_operations(reopened, result, completed, failed=failed)
    assert set(recorded) == {op1, op2}

    results = [r for r in _journal(reopened, job.job_id) if isinstance(r, OpResultRecord)]
    assert len(results) == 2  # noqa: PLR2004
    by_op = {r.operation_id: r for r in results}
    assert by_op[op1].ok is True
    assert by_op[op1].recovered is True
    assert by_op[op1].error_code is None

    assert by_op[op2].ok is False
    assert by_op[op2].recovered is True
    assert by_op[op2].error_code == "BACKEND_REBUILD_ERROR"
