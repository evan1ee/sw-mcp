"""Job records, the journal and the 8.4 transition table (spec 13.2.2, 13.2.3, 8.4)."""

import itertools
import json

import pytest
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JOB_STATES, JobRecord, JobState
from cad_application.store.journal import InvalidTransition, transition
from cad_application.store.journal_records import (
    BatchSentRecord,
    DocumentRecord,
    JournalRecord,
    NoteRecord,
    OpResultRecord,
    SnapshotRecord,
    StateRecord,
)
from cad_application.testing.builders import STORE_DIR, new_job, open_store
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem, SimulatedCrash
from cad_ir.core.json_types import JsonValue

TWO = 2
ERROR: dict[str, JsonValue] = {
    "code": "EXEC_INTERRUPTED",
    "message": "interrupted",
    "retryable": "after_fix",
}

# The edges of the 8.4 state diagram, copied from the specification.
ALLOWED: set[tuple[JobState, JobState]] = {
    ("PLANNED", "VALIDATED"),
    ("VALIDATED", "EXECUTING"),
    ("EXECUTING", "VERIFYING"),
    ("VERIFYING", "COMMITTED"),
    ("VERIFYING", "EXECUTING"),
    ("PLANNED", "FAILED"),
    ("VALIDATED", "FAILED"),
    ("EXECUTING", "FAILED"),
    ("VERIFYING", "FAILED"),
    ("PLANNED", "ABORTED"),
    ("VALIDATED", "ABORTED"),
    ("EXECUTING", "ABORTED"),
    ("VERIFYING", "ABORTED"),
    ("FAILED", "RECOVERY"),
    ("RECOVERY", "EXECUTING"),
    ("RECOVERY", "ABORTED"),
}


class _CrashOnJobJson(MemoryFileSystem):
    """Dies when job.json is replaced, once armed: the state record is already on disk."""

    def __init__(self) -> None:
        super().__init__()
        self.armed = False

    def write_atomic(self, path: str, data: bytes) -> None:
        if self.armed and path.lower().endswith("job.json"):
            raise SimulatedCrash("job.json")
        super().write_atomic(path, data)


def _setup(
    fs: MemoryFileSystem | None = None,
) -> tuple[FileStore, MemoryFileSystem, FakeClock, JobRecord]:
    fs = fs or MemoryFileSystem()
    clock = FakeClock()
    store = open_store(fs, clock)
    job = new_job(SequentialIdSource(), clock)
    store.create_job(job)
    return store, fs, clock, job


def _states(store: FileStore, job_id: str) -> list[StateRecord]:
    journal = store.read_journal(job_id)
    assert not isinstance(journal, StoreError)
    return [r for r in journal if isinstance(r, StateRecord)]


def test_create_job_writes_first_state_record_and_job_json() -> None:
    store, _, _, job = _setup()
    assert store.get_job(job.job_id) == job
    first = _states(store, job.job_id)
    assert [(r.from_state, r.to) for r in first] == [(None, "PLANNED")]
    assert store.list_jobs() == (job,)
    assert store.has_job(job.job_id)


def test_create_job_journal_precedes_job_json() -> None:
    fs = _CrashOnJobJson()
    fs.armed = True
    store = open_store(fs, FakeClock())
    job = new_job(SequentialIdSource(), FakeClock())
    with pytest.raises(SimulatedCrash):
        store.create_job(job)
    assert [(r.from_state, r.to) for r in _states(store, job.job_id)] == [(None, "PLANNED")]


def test_state_record_precedes_job_json() -> None:
    fs = _CrashOnJobJson()
    store, _, _, job = _setup(fs)
    fs.armed = True
    with pytest.raises(SimulatedCrash):
        transition(store, job, "VALIDATED", "backend acquired")
    assert _states(store, job.job_id)[-1].to == "VALIDATED"  # journal first
    assert store.get_job(job.job_id) == job  # job.json still the old state


def test_transition_returns_new_record_and_logs_it() -> None:
    store, _, clock, job = _setup()
    clock.advance(1.5)
    validated = transition(store, job, "VALIDATED", "backend acquired")
    assert job.state == "PLANNED"
    assert validated.state == "VALIDATED"
    assert validated.started_at == "2026-11-04T09:00:01.500Z"
    assert validated.ended_at is None
    failed = transition(store, validated, "FAILED", "lost", ERROR)
    assert failed.ended_at == "2026-11-04T09:00:01.500Z"
    assert failed.error == ERROR
    assert store.get_job(job.job_id) == failed
    last = _states(store, job.job_id)[-1]
    assert (last.from_state, last.to, last.reason, last.error) == (
        "VALIDATED",
        "FAILED",
        "lost",
        ERROR,
    )


def test_invalid_transition_raises_and_writes_nothing() -> None:
    store, _, _, job = _setup()
    before = store.read_journal(job.job_id)
    with pytest.raises(InvalidTransition):
        transition(store, job, "COMMITTED", "skipping ahead")
    assert store.read_journal(job.job_id) == before
    assert store.get_job(job.job_id) == job


@pytest.mark.parametrize(("start", "end"), list(itertools.product(JOB_STATES, JOB_STATES)))
def test_every_8_4_transition_allowed(start: JobState, end: JobState) -> None:
    store, _, _, job = _setup()
    current = JobRecord.from_json(job.to_json() | {"state": start})  # a record in state `start`
    before = store.read_journal(job.job_id)
    if (start, end) in ALLOWED:
        moved = transition(store, current, end, "test")
        assert moved.state == end
        assert len(_states(store, job.job_id)) == TWO
    else:
        with pytest.raises(InvalidTransition):
            transition(store, current, end, "test")
        assert store.read_journal(job.job_id) == before


def test_every_journal_record_type_round_trips() -> None:
    store, _, _, job = _setup()
    ts = "2026-11-04T09:00:00.000Z"
    records: list[JournalRecord] = [
        BatchSentRecord(ts, job.job_id, 1, (f"{job.job_id}:1",), ("C:\\Work\\a.slddrw",)),
        OpResultRecord(ts, job.job_id, f"{job.job_id}:1", True, None),
        OpResultRecord(ts, job.job_id, f"{job.job_id}:2", False, "EXEC_TIMEOUT", recovered=True),
        SnapshotRecord(ts, job.job_id, "snap_" + "0" * 26, None),
        DocumentRecord(ts, job.job_id, "C:\\Work\\a.slddrw", "open", True),
        NoteRecord(ts, job.job_id, "something worth keeping"),
    ]
    for record in records:
        store.append(job.job_id, record)
    journal = store.read_journal(job.job_id)
    assert isinstance(journal, tuple)
    assert list(journal[1:]) == records


def test_torn_last_line_ignored() -> None:
    store, fs, _, job = _setup()
    path = f"{STORE_DIR}\\jobs\\{job.job_id}\\journal.jsonl"
    intact = fs.read_bytes(path)
    fs.write_atomic(path, intact + b'{"type":"state","ts":"2026-1')  # a crash mid-append
    journal = store.read_journal(job.job_id)
    assert isinstance(journal, tuple)
    assert len(journal) == 1
    fs.drop_locks()  # the process restarts
    reopened = open_store(fs, FakeClock())
    reopened.append(job.job_id, NoteRecord("2026-11-04T09:00:00.000Z", job.job_id, "after"))
    again = reopened.read_journal(job.job_id)
    assert isinstance(again, tuple)
    assert len(again) == TWO
    assert fs.read_bytes(path).startswith(intact)


def test_corrupt_middle_line_is_store_corrupt() -> None:
    store, fs, _, job = _setup()
    path = f"{STORE_DIR}\\jobs\\{job.job_id}\\journal.jsonl"
    intact = fs.read_bytes(path).decode()
    note = json.dumps(
        {"type": "note", "ts": "2026-11-04T09:00:00.000Z", "job_id": job.job_id, "message": "m"}
    )
    fs.write_atomic(path, (intact + "garbage\n" + note + "\n").encode())
    result = store.read_journal(job.job_id)
    assert isinstance(result, StoreError)
    assert result.code == "STORE_CORRUPT"
    assert "garbage" not in result.message


def test_unknown_job_has_no_record_and_empty_journal() -> None:
    store, _, _, _ = _setup()
    assert store.get_job("job_" + "Z" * 26) is None
    assert store.read_journal("job_" + "Z" * 26) == ()
