"""Retention, spec 13.2.4."""

from dataclasses import replace

from cad_application.config import Settings
from cad_application.store.codec import format_ts
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord, JobState
from cad_application.store.journal import transition
from cad_application.store.records import DrawingRecord, ReportMeta
from cad_application.store.retention import clean_up
from cad_application.testing.builders import new_job, open_store
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_ir.core.json_types import JsonValue

DAY = 86400.0
FP = "sha256:" + "a" * 64
SETTINGS = Settings(job_retention_days=7, snapshot_keep=3)


class _Env:
    def __init__(self) -> None:
        self.fs = MemoryFileSystem()
        self.clock = FakeClock()
        self.ids = SequentialIdSource()
        self.store: FileStore = open_store(self.fs, self.clock)

    def drawing(self, *, snapshot: str | None = None, report: str | None = None) -> DrawingRecord:
        record = DrawingRecord(
            self.ids.new_id("drw"),
            "C:\\Work\\a.slddrw",
            FP,
            False,
            None,
            snapshot,
            report,
            format_ts(self.clock.now()),
        )
        self.store.put_drawing(record)
        return record

    def snapshot(self, drawing_id: str) -> str:
        snap_id = self.ids.new_id("snap")
        self.store.put_snapshot(drawing_id, snap_id, {"n": 1})
        return snap_id

    def report(self, drawing_id: str, snapshot_id: str) -> str:
        rep_id = self.ids.new_id("rep")
        meta = ReportMeta(
            rep_id, self.ids.new_id("job"), drawing_id, snapshot_id, format_ts(self.clock.now()), ()
        )
        report: JsonValue = {"verdict": "pass"}
        self.store.put_report(rep_id, report, meta)
        return rep_id

    def job(self, state: JobState) -> JobRecord:
        job = new_job(self.ids, self.clock)
        self.store.create_job(job)
        if state == "PLANNED":
            return job
        job = transition(self.store, job, "VALIDATED", "t")
        if state == "VALIDATED":
            return job
        return transition(self.store, job, state, "t")

    def age(self, days: float) -> None:
        self.clock.advance(days * DAY)


def _snapshots(env: _Env, drawing_id: str) -> tuple[str, ...]:
    return env.store.list_snapshot_ids(drawing_id)


def test_retention_keeps_referenced() -> None:
    env = _Env()
    drawing = env.drawing()
    old_snap = env.snapshot(drawing.drawing_id)
    kept_report = env.report(drawing.drawing_id, old_snap)  # the drawing record refers to it
    lone_snap = env.snapshot(drawing.drawing_id)
    other_report = env.report(drawing.drawing_id, lone_snap)  # nothing refers to it
    env.store.put_drawing(replace(drawing, latest_report_id=kept_report))
    env.age(30)
    result = clean_up(env.store, env.clock, Settings(job_retention_days=7, snapshot_keep=0))
    assert result.deleted_reports == (other_report,)
    assert env.store.get_report(kept_report) is not None
    assert env.store.get_report(other_report) is None
    assert _snapshots(env, drawing.drawing_id) == (old_snap,)  # referenced by the kept report
    assert result.deleted_snapshots == ((drawing.drawing_id, lone_snap),)


def test_retention_keeps_snapshot_of_recent_report() -> None:
    env = _Env()
    drawing = env.drawing()
    snap = env.snapshot(drawing.drawing_id)
    report = env.report(drawing.drawing_id, snap)
    env.age(6)
    clean_up(env.store, env.clock, Settings(job_retention_days=7, snapshot_keep=0))
    assert env.store.get_report(report) is not None
    assert _snapshots(env, drawing.drawing_id) == (snap,)


def test_retention_keeps_last_n_snapshots_per_drawing() -> None:
    env = _Env()
    first, second = env.drawing(), env.drawing()
    firsts = [env.snapshot(first.drawing_id) for _ in range(5)]
    seconds = [env.snapshot(second.drawing_id) for _ in range(2)]
    env.age(30)
    result = clean_up(env.store, env.clock, SETTINGS)
    assert _snapshots(env, first.drawing_id) == tuple(firsts[-3:])
    assert _snapshots(env, second.drawing_id) == tuple(seconds)
    assert result.deleted_snapshots == tuple((first.drawing_id, s) for s in firsts[:2])


def test_retention_never_deletes_running_job() -> None:
    env = _Env()
    drawing = env.drawing()
    running = env.job("EXECUTING")
    queued = env.job("PLANNED")
    snap = env.snapshot(drawing.drawing_id)
    # A stale ended_at must not matter: only the state decides.
    stale_end = {"snapshot_id": snap, "ended_at": "2026-01-01T00:00:00.000Z"}
    env.store.put_job(JobRecord.from_json(running.to_json() | stale_end))
    env.age(365)
    result = clean_up(env.store, env.clock, Settings(job_retention_days=7, snapshot_keep=0))
    assert result.deleted_jobs == ()
    assert env.store.get_job(running.job_id) is not None
    assert env.store.get_job(queued.job_id) is not None
    assert _snapshots(env, drawing.drawing_id) == (snap,)  # a non-final job refers to it


def test_retention_age_from_ended_at() -> None:
    env = _Env()
    recent = env.job("FAILED")  # created long ago, ended just now
    stale = env.job("FAILED")
    env.age(8)
    recent_now = env.job("FAILED")
    old_created = env.store.get_job(recent.job_id)
    assert isinstance(old_created, JobRecord)
    # `recent` was created 8 days ago; only its ended_at (now) keeps it.
    env.store.put_job(
        JobRecord.from_json(old_created.to_json() | {"ended_at": format_ts(env.clock.now())})
    )
    result = clean_up(env.store, env.clock, SETTINGS)
    assert result.deleted_jobs == (stale.job_id,)
    assert env.store.get_job(recent.job_id) is not None
    assert env.store.get_job(recent_now.job_id) is not None


def test_expired_report_not_found() -> None:
    env = _Env()
    drawing = env.drawing()
    snap = env.snapshot(drawing.drawing_id)
    report = env.report(drawing.drawing_id, snap)
    job = env.job("FAILED")
    env.age(8)
    clean_up(env.store, env.clock, SETTINGS)
    assert env.store.get_report(report) is None
    assert not env.store.has_report(report)
    assert env.store.get_job(job.job_id) is None
    assert not env.store.has_job(job.job_id)


def test_retention_stops_on_corrupt_drawing_record() -> None:
    env = _Env()
    drawing = env.drawing()
    snap = env.snapshot(drawing.drawing_id)
    env.report(drawing.drawing_id, snap)
    env.fs.write_atomic(f"C:\\Work\\.cad\\drawings\\{drawing.drawing_id}.json", b"{")
    env.age(30)
    result = clean_up(env.store, env.clock, SETTINGS)
    assert isinstance(result.error, StoreError)
    assert result.deleted_reports == ()
    assert result.deleted_snapshots == ()
