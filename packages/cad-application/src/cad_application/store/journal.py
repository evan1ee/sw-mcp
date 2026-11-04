"""Job transitions and crash recovery (spec 8.4, 13.2.2, 13.2.3 Phase 1a)."""

import ntpath
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final

from cad_ir.generated.error_codes import DEFAULT_RETRYABLE, ErrorCode

from cad_application.ports import Clock, Store
from cad_application.store.codec import Obj, format_ts
from cad_application.store.errors import StoreError
from cad_application.store.job_records import FINAL_STATES, JobDocument, JobRecord, JobState
from cad_application.store.journal_records import (
    BatchSentRecord,
    DocumentRecord,
    OpResultRecord,
    StateRecord,
)

# The edges of the 8.4 state diagram; any other transition is a programming error.
TRANSITIONS: Final[Mapping[JobState, frozenset[JobState]]] = MappingProxyType(
    {
        "PLANNED": frozenset({"VALIDATED", "FAILED", "ABORTED"}),
        "VALIDATED": frozenset({"EXECUTING", "FAILED", "ABORTED"}),
        "EXECUTING": frozenset({"VERIFYING", "FAILED", "ABORTED"}),
        "VERIFYING": frozenset({"COMMITTED", "EXECUTING", "FAILED", "ABORTED"}),
        "FAILED": frozenset({"RECOVERY"}),
        "RECOVERY": frozenset({"EXECUTING", "ABORTED"}),
        "COMMITTED": frozenset(),
        "ABORTED": frozenset(),
    }
)
_STARTED: Final[frozenset[JobState]] = frozenset(
    {"VALIDATED", "EXECUTING", "VERIFYING", "RECOVERY"}
)


class InvalidTransition(Exception):  # noqa: N818 - names the programming error it reports
    def __init__(self, from_state: JobState, to: JobState) -> None:
        super().__init__(f"transition {from_state} -> {to} is not in the 8.4 table")
        self.from_state = from_state
        self.to = to


def apply_state(job: JobRecord, to: JobState, ts: str, error: Obj | None) -> JobRecord:
    """The job record after entering ``to`` at ``ts``; the input is not changed."""
    started = job.started_at if job.started_at is not None or to not in _STARTED else ts
    ended = ts if to in FINAL_STATES else job.ended_at
    return replace(job, state=to, started_at=started, ended_at=ended, error=error)


def _enter(store: Store, job: JobRecord, record: StateRecord) -> JobRecord:
    if record.to not in TRANSITIONS[job.state]:
        raise InvalidTransition(job.state, record.to)
    # Journal first (13.2.2): a crash between the two leaves the journal one step ahead.
    store.append(job.job_id, record)
    moved = apply_state(job, record.to, record.ts, record.error)
    store.put_job(moved)
    return moved


def transition(
    store: Store, job: JobRecord, to: JobState, reason: str, error: Obj | None = None
) -> JobRecord:
    """Validate against the 8.4 table, append the ``state`` record, replace ``job.json``."""
    record = StateRecord(store.timestamp(), job.job_id, job.state, to, reason, error)
    return _enter(store, job, record)


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    """What recovery did. ``orphans`` are job folders without a readable ``job.json``;
    ``corrupt`` are jobs whose records failed an integrity check (both left untouched)."""

    interrupted: tuple[JobRecord, ...]
    reconciled: tuple[str, ...]
    pending_operation_ids: Mapping[str, tuple[str, ...]]
    corrupt: tuple[str, ...]
    orphans: tuple[str, ...]


def _interrupted_error() -> Obj:
    return {
        "code": ErrorCode.EXEC_INTERRUPTED.value,
        "message": "The job was interrupted before it finished; its outcome is unknown.",
        "retryable": DEFAULT_RETRYABLE[ErrorCode.EXEC_INTERRUPTED],
    }


def _unknown_documents(journal: Sequence[object]) -> tuple[JobDocument, ...]:
    """Documents with an ``open`` record and no later ``close`` (13.2.3)."""
    open_now: dict[str, JobDocument] = {}
    for record in journal:
        if not isinstance(record, DocumentRecord):
            continue
        key = ntpath.normcase(record.path)
        if record.action == "open":
            open_now[key] = JobDocument(record.path, record.owned, "unknown")
        elif record.action == "close":
            open_now.pop(key, None)
    return tuple(open_now.values())


def _unanswered(journal: Sequence[object]) -> tuple[str, ...]:
    answered = {r.operation_id for r in journal if isinstance(r, OpResultRecord)}
    sent = [op for r in journal if isinstance(r, BatchSentRecord) for op in r.operation_ids]
    return tuple(op for op in sent if op not in answered)


def _journal_chain(job: JobRecord, journal: Sequence[object]) -> tuple[StateRecord, ...] | None:
    """The ``state`` records after the one that made ``job.json`` current: empty when the two
    agree, None when they do not form a legal chain of the 8.4 table starting there."""
    states = [r for r in journal if isinstance(r, StateRecord)]
    if not states or states[-1].to == job.state:
        return ()
    reached = [i for i, r in enumerate(states) if r.to == job.state]
    if not reached:
        return None
    current, chain = job.state, states[reached[-1] + 1 :]
    for step in chain:
        if step.from_state != current or step.to not in TRANSITIONS[current]:
            return None
        current = step.to
    return tuple(chain)


def recover(store: Store, clock: Clock) -> RecoveryResult:
    """Steps 1, 3 and 4 of 13.2.3, after the order rule of 13.2.2. Never resumes or resends."""
    ts = format_ts(clock.now())
    interrupted: list[JobRecord] = []
    reconciled: list[str] = []
    pending: dict[str, tuple[str, ...]] = {}
    corrupt: list[str] = []
    orphans: list[str] = []
    for job_id in store.list_job_ids():
        job = store.get_job(job_id)
        journal = store.read_journal(job_id)
        if job is None:
            orphans.append(job_id)
            continue
        if isinstance(job, StoreError) or isinstance(journal, StoreError):
            corrupt.append(job_id)
            continue
        ahead = _journal_chain(job, journal)
        if ahead is None:  # not reachable from job.json by the 8.4 table (13.2.3)
            corrupt.append(job_id)
            continue
        if ahead:  # the journal wins
            for step in ahead:
                job = apply_state(job, step.to, step.ts, step.error)
            store.put_job(job)
            reconciled.append(job_id)
        if job.is_final or job.state == "RECOVERY":
            continue
        target: JobState = "ABORTED" if job.state == "PLANNED" else "FAILED"
        with_documents = replace(job, documents=_unknown_documents(journal))
        reason = "core service restarted while the job was not finished"
        record = StateRecord(ts, job_id, job.state, target, reason, _interrupted_error())
        interrupted.append(_enter(store, with_documents, record))
        if ops := _unanswered(journal):
            pending[job_id] = ops
    return RecoveryResult(
        tuple(interrupted),
        tuple(reconciled),
        MappingProxyType(pending),
        tuple(corrupt),
        tuple(orphans),
    )


def record_completed_operations(
    store: Store, result: RecoveryResult, completed: Sequence[str]
) -> tuple[str, ...]:
    """Step 2: ``op_result`` with ``recovered: true`` for pending IDs the add-in completed."""
    done = set(completed)
    recorded: list[str] = []
    for job_id, pending in result.pending_operation_ids.items():
        journal = store.read_journal(job_id)
        if isinstance(journal, StoreError):
            continue
        for op in _unanswered(journal):
            if op in pending and op in done:
                ts = store.timestamp()
                store.append(job_id, OpResultRecord(ts, job_id, op, True, None, recovered=True))
                recorded.append(op)
    return tuple(recorded)
