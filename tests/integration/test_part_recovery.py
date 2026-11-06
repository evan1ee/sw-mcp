"""Integration tests for part crash recovery (spec 8.4, 13.2.3, ADR-064)."""

import pytest
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord
from cad_application.store.journal import recover, transition
from cad_application.store.journal_records import (
    BatchSentRecord,
    DocumentRecord,
    JournalRecord,
    OpResultRecord,
    OpVerifiedRecord,
    PublishedRecord,
    PublishIntentRecord,
    StateRecord,
)
from cad_application.testing.builders import open_store
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem

TS = "2026-11-04T09:00:00.000Z"
FP_MATCH = "sha256:" + "a" * 64
FP_DIFF = "sha256:" + "b" * 64

WORKING_PATH = "C:\\Work\\bracket.job_01H1234567890ABCDEFGHJKMNP.building.SLDPRT"
TARGET_PATH = "C:\\Work\\bracket.SLDPRT"


def _env() -> tuple[FileStore, MemoryFileSystem, FakeClock, SequentialIdSource]:
    fs = MemoryFileSystem()
    clock = FakeClock()
    return open_store(fs, clock), fs, clock, SequentialIdSource()


def _restart(fs: MemoryFileSystem, clock: FakeClock) -> FileStore:
    fs.drop_locks()
    return open_store(fs, clock)


def _journal(store: FileStore, job_id: str) -> tuple[JournalRecord, ...]:
    journal = store.read_journal(job_id)
    assert not isinstance(journal, StoreError)
    return journal


def _create_part_job(store: FileStore, ids: SequentialIdSource, clock: FakeClock) -> JobRecord:
    job_id = ids.new_id("job")
    record = JobRecord(
        job_id=job_id,
        job_type="plan",
        state="PLANNED",
        created_at=TS,
        started_at=None,
        ended_at=None,
        request_id=ids.new_id("req"),
        arguments={"target_path": TARGET_PATH, "graph": "part:bracket@1"},
        project_root="C:\\Work",
        drawing_id=None,
        fingerprint=None,
        progress=None,
        snapshot_id=None,
        report_id=None,
        error=None,
        warnings=(),
        documents=(),
        next_op_seq=1,
    )
    store.create_job(record)
    return record


@pytest.mark.parametrize(
    ("crash_point", "expect_working_unknown", "expect_pending_ops"),
    [
        ("before_part_create", False, False),
        ("after_part_create", True, False),
        ("after_operation", True, True),
        ("after_publish_intent_no_rename", True, False),
        ("after_rename_no_published", True, False),
        ("before_committed", True, False),
    ],
)
def test_crash_points(
    crash_point: str, expect_working_unknown: bool, expect_pending_ops: bool
) -> None:
    store, fs, clock, ids = _env()
    job = _create_part_job(store, ids, clock)
    job_id = job.job_id

    # Move to VALIDATED then EXECUTING
    job = transition(store, job, "VALIDATED", "validation ok")
    job = transition(store, job, "EXECUTING", "start ops")

    target_fingerprint_for_recovery: str | None = None

    if crash_point == "before_part_create":
        # Crash right after entering EXECUTING before document create
        pass
    elif crash_point == "after_part_create":
        # Working part created
        store.append(
            job_id,
            DocumentRecord(TS, job_id, WORKING_PATH, "create", True),
        )
    elif crash_point == "after_operation":
        store.append(
            job_id,
            DocumentRecord(TS, job_id, WORKING_PATH, "create", True),
        )
        op1, op2 = f"{job_id}:1", f"{job_id}:2"
        store.append(job_id, BatchSentRecord(TS, job_id, 1, (op1,), (WORKING_PATH,)))
        store.append(job_id, OpResultRecord(TS, job_id, op1, True, None))
        store.append(
            job_id,
            OpVerifiedRecord(
                ts=TS,
                job_id=job_id,
                operation_id=op1,
                node="sketch_base",
                feature_id="f1",
                observation=None,
                checks=(),
                status="passed",
            ),
        )
        store.append(job_id, BatchSentRecord(TS, job_id, 2, (op2,), (WORKING_PATH,)))
        # Crash with op2 pending (sent but no result)
    elif crash_point in (
        "after_publish_intent_no_rename",
        "after_rename_no_published",
        "before_committed",
    ):
        store.append(
            job_id,
            DocumentRecord(TS, job_id, WORKING_PATH, "create", True),
        )
        job = transition(store, job, "VERIFYING", "ops complete")
        store.append(
            job_id,
            PublishIntentRecord(TS, job_id, TARGET_PATH, FP_MATCH),
        )

        if crash_point == "after_publish_intent_no_rename":
            # File has not been renamed; target does not exist
            target_fingerprint_for_recovery = None
        elif crash_point == "after_rename_no_published":
            # File renamed to target path, but crash occurred before published record
            target_fingerprint_for_recovery = FP_MATCH
        elif crash_point == "before_committed":
            # File renamed, published record written, but crashed before COMMITTED
            target_fingerprint_for_recovery = FP_MATCH
            store.append(
                job_id,
                PublishedRecord(TS, job_id, TARGET_PATH, FP_MATCH),
            )

    # Simulated crash: restart and recover
    reopened = _restart(fs, clock)

    def read_fp(path: str) -> str | None:
        if path == TARGET_PATH:
            return target_fingerprint_for_recovery
        return None

    result = recover(reopened, clock, read_fp)

    saved = reopened.get_job(job_id)
    assert isinstance(saved, JobRecord)
    assert saved.state == "FAILED"
    assert saved.error is not None
    assert saved.error["code"] == "EXEC_INTERRUPTED"

    if expect_working_unknown:
        assert [(d.path, d.owned, d.state) for d in saved.documents] == [
            (WORKING_PATH, True, "unknown")
        ]
    else:
        assert saved.documents == ()

    if expect_pending_ops:
        assert result.pending_operation_ids.get(job_id) == (f"{job_id}:2",)
    else:
        assert job_id not in result.pending_operation_ids

    # Never resends: journal ends with state FAILED
    last = _journal(reopened, job_id)[-1]
    assert isinstance(last, StateRecord)
    assert last.to == "FAILED"


def test_published_unconfirmed() -> None:
    # Scenario A: Matching target fingerprint adds published_unconfirmed warning
    store, fs, clock, ids = _env()
    job_a = _create_part_job(store, ids, clock)
    job_a = transition(store, job_a, "VALIDATED", "ok")
    job_a = transition(store, job_a, "EXECUTING", "ok")
    store.append(job_a.job_id, DocumentRecord(TS, job_a.job_id, WORKING_PATH, "create", True))
    job_a = transition(store, job_a, "VERIFYING", "ok")
    store.append(job_a.job_id, PublishIntentRecord(TS, job_a.job_id, TARGET_PATH, FP_MATCH))

    reopened_a = _restart(fs, clock)
    recover(reopened_a, clock, read_fingerprint=lambda p: FP_MATCH if p == TARGET_PATH else None)
    saved_a = reopened_a.get_job(job_a.job_id)
    assert isinstance(saved_a, JobRecord)
    assert saved_a.state == "FAILED"
    assert any(
        w.code == "published_unconfirmed" and TARGET_PATH in w.message for w in saved_a.warnings
    )
    # File is not adopted and no part record is written
    assert reopened_a.get_part_record("fp-match") is None

    # Scenario B: Differing fingerprint adds NO warning
    store_b, fs_b, clock_b, ids_b = _env()
    job_b = _create_part_job(store_b, ids_b, clock_b)
    job_b = transition(store_b, job_b, "VALIDATED", "ok")
    job_b = transition(store_b, job_b, "EXECUTING", "ok")
    store_b.append(job_b.job_id, DocumentRecord(TS, job_b.job_id, WORKING_PATH, "create", True))
    job_b = transition(store_b, job_b, "VERIFYING", "ok")
    store_b.append(job_b.job_id, PublishIntentRecord(TS, job_b.job_id, TARGET_PATH, FP_MATCH))

    reopened_b = _restart(fs_b, clock_b)
    recover(reopened_b, clock_b, read_fingerprint=lambda p: FP_DIFF if p == TARGET_PATH else None)
    saved_b = reopened_b.get_job(job_b.job_id)
    assert isinstance(saved_b, JobRecord)
    assert saved_b.state == "FAILED"
    assert not any(w.code == "published_unconfirmed" for w in saved_b.warnings)

    # Scenario C: Missing target file (None) adds NO warning
    store_c, fs_c, clock_c, ids_c = _env()
    job_c = _create_part_job(store_c, ids_c, clock_c)
    job_c = transition(store_c, job_c, "VALIDATED", "ok")
    job_c = transition(store_c, job_c, "EXECUTING", "ok")
    store_c.append(job_c.job_id, DocumentRecord(TS, job_c.job_id, WORKING_PATH, "create", True))
    job_c = transition(store_c, job_c, "VERIFYING", "ok")
    store_c.append(job_c.job_id, PublishIntentRecord(TS, job_c.job_id, TARGET_PATH, FP_MATCH))

    reopened_c = _restart(fs_c, clock_c)
    recover(reopened_c, clock_c, read_fingerprint=lambda _: None)
    saved_c = reopened_c.get_job(job_c.job_id)
    assert isinstance(saved_c, JobRecord)
    assert saved_c.state == "FAILED"
    assert not any(w.code == "published_unconfirmed" for w in saved_c.warnings)
