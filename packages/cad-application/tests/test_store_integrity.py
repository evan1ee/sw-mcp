"""Strict JSON, nesting limits, job identity and legal-only recovery (13.2.2, 13.2.3; J13, J18)."""

import pytest
from cad_application.store.codec import decode_json, encode, encode_line
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord
from cad_application.store.journal import recover, transition
from cad_application.store.journal_records import StateRecord
from cad_application.testing.builders import STORE_DIR, new_job, open_store
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem

TS = "2026-11-04T09:00:00.000Z"
DEEP = 100_000


def _env() -> tuple[FileStore, MemoryFileSystem, FakeClock, SequentialIdSource]:
    fs, clock = MemoryFileSystem(), FakeClock()
    return open_store(fs, clock), fs, clock, SequentialIdSource()


def _job_path(job: JobRecord, name: str = "job.json") -> str:
    return STORE_DIR + chr(92) + "jobs" + chr(92) + job.job_id + chr(92) + name


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_encode_refuses_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValueError, match="range"):
        encode({"n": value})
    with pytest.raises(ValueError, match="range"):
        encode_line({"n": value})


def test_deeply_nested_json_is_unreadable() -> None:
    result = decode_json(b"[" * DEEP + b"]" * DEEP, "x.json")
    assert isinstance(result, StoreError)
    assert result.code == "STORE_CORRUPT"


def test_deep_job_json_is_corrupt() -> None:
    store, fs, clock, ids = _env()
    job = new_job(ids, clock)
    store.create_job(job)
    fs.write_atomic(_job_path(job), b"[" * DEEP)
    found = store.get_job(job.job_id)
    assert isinstance(found, StoreError)
    assert found.code == "STORE_CORRUPT"
    assert recover(store, clock).corrupt == (job.job_id,)


def test_job_id_folder_mismatch_corrupt() -> None:
    store, fs, clock, ids = _env()
    first, second = new_job(ids, clock), new_job(ids, clock)
    store.create_job(first)
    store.create_job(second)
    fs.write_atomic(_job_path(second), fs.read_bytes(_job_path(first)))
    found = store.get_job(second.job_id)
    assert isinstance(found, StoreError)
    assert found.code == "STORE_CORRUPT"
    assert store.get_job(first.job_id) == first


def test_journal_ignores_illegal_transition_after_final() -> None:
    store, fs, clock, ids = _env()
    job = new_job(ids, clock)
    store.create_job(job)
    job = transition(store, job, "VALIDATED", "t")
    job = transition(store, job, "EXECUTING", "t")
    job = transition(store, job, "VERIFYING", "t")
    job = transition(store, job, "COMMITTED", "t")
    stray = StateRecord(TS, job.job_id, "COMMITTED", "EXECUTING", "stray")
    store.append(job.job_id, stray)
    fs.drop_locks()
    reopened = open_store(fs, clock)
    result = recover(reopened, clock)
    assert reopened.get_job(job.job_id) == job  # still COMMITTED
    assert result.interrupted == ()
    assert result.reconciled == ()
    assert result.corrupt == (job.job_id,)


def test_journal_chain_of_legal_records_wins() -> None:
    store, fs, clock, ids = _env()
    job = new_job(ids, clock)
    store.create_job(job)
    job = transition(store, job, "VALIDATED", "t")
    store.append(job.job_id, StateRecord(TS, job.job_id, "VALIDATED", "EXECUTING", "t"))
    store.append(job.job_id, StateRecord(TS, job.job_id, "EXECUTING", "FAILED", "lost"))
    fs.drop_locks()
    result = recover(open_store(fs, clock), clock)
    assert result.reconciled == (job.job_id,)
    assert result.corrupt == ()
