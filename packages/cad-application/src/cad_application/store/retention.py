"""Clean-up of jobs, reports and snapshots (spec 13.2.4)."""

from dataclasses import dataclass
from datetime import timedelta

from cad_application.config import Settings
from cad_application.ports import Clock, Store
from cad_application.store.codec import parse_ts
from cad_application.store.errors import StoreError
from cad_application.store.job_records import JobRecord


@dataclass(frozen=True, slots=True)
class CleanUpResult:
    deleted_jobs: tuple[str, ...] = ()
    deleted_reports: tuple[str, ...] = ()
    deleted_snapshots: tuple[tuple[str, str], ...] = ()
    error: StoreError | None = None


def _jobs(store: Store) -> tuple[JobRecord, ...]:
    """Readable jobs; a corrupt or orphaned job folder is never deleted."""
    found = (store.get_job(job_id) for job_id in store.list_job_ids())
    return tuple(job for job in found if isinstance(job, JobRecord))


def clean_up(store: Store, clock: Clock, settings: Settings) -> CleanUpResult:
    """Delete only what nothing kept refers to. Stops without deleting if a record is corrupt."""
    drawings = store.list_drawings()
    metas = store.list_report_metas()
    if isinstance(drawings, StoreError):
        return CleanUpResult(error=drawings)
    if isinstance(metas, StoreError):
        return CleanUpResult(error=metas)
    cutoff = clock.now() - timedelta(days=settings.job_retention_days)
    jobs = _jobs(store)
    open_jobs = [j for j in jobs if not j.is_final]
    keep_reports = {d.latest_report_id for d in drawings} | {j.report_id for j in open_jobs}
    expired_reports = tuple(
        m.report_id
        for m in metas
        if m.report_id not in keep_reports and parse_ts(m.created_at) < cutoff
    )
    kept_metas = [m for m in metas if m.report_id not in expired_reports]
    keep_snapshots = (
        {d.latest_snapshot_id for d in drawings}
        | {j.snapshot_id for j in open_jobs}
        | {m.snapshot_id for m in kept_metas}
    )
    expired_jobs = tuple(
        j.job_id
        for j in jobs
        if j.is_final and j.ended_at is not None and parse_ts(j.ended_at) < cutoff
    )
    expired_snapshots: list[tuple[str, str]] = []
    for drawing in drawings:
        ranked = store.list_snapshot_ids(drawing.drawing_id)  # ULIDs sort by time
        newest = set(ranked[max(0, len(ranked) - settings.snapshot_keep) :])
        expired_snapshots.extend(
            (drawing.drawing_id, s) for s in ranked if s not in newest and s not in keep_snapshots
        )
    for report_id in expired_reports:
        store.delete_report(report_id)
    for drawing_id, snapshot_id in expired_snapshots:
        store.delete_snapshot(drawing_id, snapshot_id)
    for job_id in expired_jobs:
        store.delete_job(job_id)
    return CleanUpResult(expired_jobs, expired_reports, tuple(expired_snapshots))
