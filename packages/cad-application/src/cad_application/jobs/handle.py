"""A job's entry in the engine and the handle a running job uses (ADR-053).

The engine's condition guards every state change: the journal record is appended, ``job.json``
replaced, memory updated and waiters woken inside one critical section. A ``Backend`` call is
never made while it is held.
"""

import threading
from collections.abc import Callable
from dataclasses import replace
from typing import cast

from cad_ir.core.json_types import JsonValue

from cad_application.jobs.model import CheckDrawingSpec, PlanSpec
from cad_application.ports import Backend, EventLog, Store
from cad_application.store.codec import Obj
from cad_application.store.job_records import JobProgress, JobRecord, JobState
from cad_application.store.journal import transition
from cad_application.store.journal_records import JournalRecord

type Notification = tuple[str, JsonValue]


class JobEntry:
    """The engine's mutable bookkeeping for one job. Fields change only under the engine lock."""

    def __init__(self, record: JobRecord, store: Store, spec: CheckDrawingSpec | PlanSpec) -> None:
        self.record = record
        self.store = store
        self.spec = spec
        self.cancel_requested = False
        self.keep_partial = False
        self.backend: Backend | None = None
        self.notifications: list[Notification] = []
        self.notes_guard = threading.Lock()


class JobHandle[S = CheckDrawingSpec]:
    """What ``check_drawing.run`` or ``plan_job.run`` sees of its job.

    Every record it returns is immutable.
    """

    def __init__(self, entry: JobEntry, cond: threading.Condition, log: EventLog) -> None:
        self._entry = entry
        self._cond = cond
        self._log = log

    @property
    def record(self) -> JobRecord:
        with self._cond:
            return self._entry.record

    @property
    def store(self) -> Store:
        return self._entry.store

    @property
    def spec(self) -> S:
        return cast("S", self._entry.spec)

    @property
    def cancel_requested(self) -> bool:
        with self._cond:
            return self._entry.cancel_requested

    @property
    def keep_partial(self) -> bool:
        with self._cond:
            return self._entry.keep_partial

    def set_backend(self, backend: Backend | None) -> None:
        with self._cond:
            self._entry.backend = backend

    def advance(self, to: JobState, reason: str, error: Obj | None = None) -> None:
        with self._cond:
            self.advance_locked(to, reason, error)

    def advance_locked(self, to: JobState, reason: str, error: Obj | None = None) -> None:
        """Like ``advance``; the caller holds the engine condition."""
        entry = self._entry
        entry.record = transition(entry.store, entry.record, to, reason, error)
        self._log.emit(
            "job.state",
            "info",
            job_id=entry.record.job_id,
            request_id=entry.record.request_id,
            state=to,
        )
        self._cond.notify_all()

    def edit(self, change: Callable[[JobRecord], JobRecord]) -> None:
        """Replace the record with ``change(record)`` and write ``job.json``."""
        with self._cond:
            entry = self._entry
            entry.record = self._store_edited(change(entry.record))
            self._cond.notify_all()

    def _store_edited(self, record: JobRecord) -> JobRecord:
        self._entry.store.put_job(record)
        return record

    def progress(self, step: int, of: int, message: str) -> None:
        self.edit(lambda r: replace(r, progress=JobProgress(step, of, message)))
        self._log.emit("job.progress", "info", job_id=self._entry.record.job_id, count=step)

    def append(self, record: JournalRecord) -> None:
        """One journal line, flushed before this returns (13.2.2)."""
        self._entry.store.append(self._entry.record.job_id, record)

    def timestamp(self) -> str:
        return self._entry.store.timestamp()

    def on_notification(self, method: str, params: JsonValue) -> None:
        """The callback given to ``BackendProvider.acquire``; may run on any thread."""
        with self._entry.notes_guard:
            self._entry.notifications.append((method, params))

    def take_notifications(self) -> tuple[Notification, ...]:
        with self._entry.notes_guard:
            taken = tuple(self._entry.notifications)
            self._entry.notifications.clear()
        return taken
