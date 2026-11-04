"""Builders for store tests: a ready FileStore and job records."""

from cad_application.ports import Clock
from cad_application.store.codec import format_ts
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord, JobState
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem

PROJECT_ROOT = "C:\\Work"
STORE_DIR = "C:\\Work\\.cad"


def open_store(fs: MemoryFileSystem, clock: Clock) -> FileStore:
    """Open (or reopen) the store of ``C:\\Work``; asserts that it opens."""
    fs.make_dirs(PROJECT_ROOT)
    opened = FileStore.open(fs, STORE_DIR, PROJECT_ROOT, clock)
    if not isinstance(opened, FileStore):
        raise AssertionError(opened)
    return opened


def new_job(ids: SequentialIdSource, clock: Clock, *, state: JobState = "PLANNED") -> JobRecord:
    """A check_drawing job record as the engine creates it."""
    return JobRecord(
        job_id=ids.new_id("job"),
        job_type="check_drawing",
        state=state,
        created_at=format_ts(clock.now()),
        started_at=None,
        ended_at=None,
        request_id=ids.new_id("req"),
        arguments={"path": "C:\\Work\\a.slddrw"},
        project_root=PROJECT_ROOT,
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
