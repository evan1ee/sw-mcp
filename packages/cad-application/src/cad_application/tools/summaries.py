"""The one-line summaries of ADR-044 (spec 12.4.5). Each is clipped to 200 characters by ``ok``."""

from collections.abc import Mapping

from cad_application.store.job_records import JobRecord

_PROGRESS_STATES = frozenset({"EXECUTING", "VERIFYING"})
_TIMES = chr(0xD7)  # the multiplication sign of the summary line (12.4.5)


def queued_line(job_id: str, position: int) -> str:
    return f"drawing check queued: {job_id} (position {position})"


def part_queued_line(job_id: str, position: int) -> str:
    return f"part build queued: {job_id} (position {position})"


def status_line(record: JobRecord, position: int | None) -> str:
    head = f"{record.job_id} {record.job_type} {record.state}"
    progress = record.progress
    if record.state in _PROGRESS_STATES and progress is not None:
        return f"{head} ({progress.step}/{progress.of} {progress.message})"
    if record.state == "PLANNED":
        return f"{head} (position {position or 0})"
    if record.state == "COMMITTED" and record.report_id is not None:
        return f"{head} (report {record.report_id})"
    if record.error is not None:
        return f"{head} ({record.error['code']})"
    return head


def cancel_line(job_id: str, state: str, *, final: bool) -> str:
    return f"{job_id} {state}" if final else f"cancel requested: {job_id} {state}"


def report_line(report_id: str, verdict: str, checks: Mapping[str, Mapping[str, object]]) -> str:
    """The line of 12.4.5: failed checks with their counts for ``fail``; for ``not_evaluated``
    the checks that were not evaluated instead."""
    if verdict == "fail":
        failed = [f"{n} {_TIMES}{c['failure_count']}" for n, c in checks.items() if _is(c, "fail")]
        return f"drawing check FAIL: {', '.join(failed)} (report {report_id})"
    if verdict == "not_evaluated":
        names = [n for n, c in checks.items() if _is(c, "not_evaluated")]
        return f"drawing check NOT EVALUATED: {', '.join(names)} (report {report_id})"
    return f"drawing check DONE (report {report_id})"


def _is(check: Mapping[str, object], status: str) -> bool:
    return check.get("status") == status


def section_line(report_id: str, section: str, shown: int, total: int) -> str:
    return f"report {report_id} {section}: {shown} of {total} items"


def no_report_line(job_id: str, state: str) -> str:
    pending = state not in ("FAILED", "ABORTED")
    return f"{job_id} {state}: no report{' yet' if pending else ''}"
