"""The job engine: a thread-safe state machine and FIFO queue (spec 8.4, ADR-053).

``run_next`` runs one queued job to its end on the calling thread; the engine never starts a
thread. Waiting goes through the ``Clock`` port, so long-polls run without real time in tests.
The lock is never held across a ``Backend`` call.
"""

import hashlib
import threading
from collections import deque
from collections.abc import Callable, Mapping

from cad_drawing.checks import TitleBlockMapping
from cad_ir.generated.error_codes import ErrorCode
from cad_ir.generated.ipc import Meta

from cad_application.config.settings import Settings
from cad_application.jobs.check_drawing import RunContext, run
from cad_application.jobs.handle import JobEntry, JobHandle
from cad_application.jobs.model import (
    CheckDrawingSpec,
    JobView,
    UnknownJobError,
    error_object,
    new_job_record,
)
from cad_application.ports import Backend, BackendProvider, Clock, EventLog, IdSource, Store
from cad_application.store.errors import StoreError
from cad_application.store.job_records import JobRecord
from cad_application.store.journal import RecoveryResult, record_completed_operations, recover
from cad_application.store.retention import clean_up
from cad_application.store.store_set import StoreSet

_MS_PER_S = 1000.0


class JobEngine:
    def __init__(  # noqa: PLR0913, PLR0917 - the engine's collaborators, all ports (G2)
        self,
        stores: StoreSet,
        provider: BackendProvider,
        clock: Clock,
        ids: IdSource,
        log: EventLog,
        settings_for: Callable[[str], Settings],
        mappings_for: Callable[[Settings], Mapping[str, TitleBlockMapping]],
    ) -> None:
        self._stores = stores
        self._provider = provider
        self._clock = clock
        self._ids = ids
        self._log = log
        self._settings_for = settings_for
        self._mappings_for = mappings_for
        self._cond = threading.Condition(threading.Lock())
        self._entries: dict[str, JobEntry] = {}
        self._queue: deque[str] = deque()
        self._running: str | None = None
        self._recovered: tuple[tuple[Store, RecoveryResult], ...] = ()
        stores.set_on_first_open(self._recover_store)

    # --- requests from any thread ------------------------------------------------------

    def submit(self, spec: CheckDrawingSpec, request_id: str) -> JobView | StoreError:
        store = self._stores.open_for(spec.authorized)
        if isinstance(store, StoreError):
            return store
        job_id = self._ids.new_id("job")
        record = new_job_record(job_id, request_id, spec, store.timestamp())
        entry = JobEntry(record, store, spec)
        with self._cond:
            store.create_job(record)
            self._entries[job_id] = entry
            self._queue.append(job_id)
            self._cond.notify_all()
            view = self._view_locked(entry)
        self._log.emit("job.submitted", "info", job_id=job_id, request_id=request_id)
        return view

    def status(self, job_id: str) -> JobView | None:
        with self._cond:
            entry = self._entries.get(job_id)
            if entry is not None:
                return self._view_locked(entry)
        return self._stored_view(job_id)

    def wait_for_change(self, job_id: str, wait_ms: int) -> tuple[JobView, bool]:
        """Returns on a state change or when the job is final; progress changes do not wake it.

        The flag is True when the state changed during the call. Raises ``UnknownJobError``.
        """
        deadline = self._clock.monotonic_s() + wait_ms / _MS_PER_S
        with self._cond:
            entry = self._entries.get(job_id)
            if entry is not None:
                return self._wait_locked(entry, deadline)
        return self._known_view(job_id), False

    def cancel(self, job_id: str) -> JobView:
        """A queued job is ABORTED at once; a running one gets its cancel flag under the lock
        and ``Backend.cancel()`` outside it (8.4, ADR-053). Raises ``UnknownJobError``."""
        with self._cond:
            entry = self._entries.get(job_id)
            if entry is not None and not entry.record.is_final:
                entry.cancel_requested = True
                if job_id in self._queue:
                    self._queue.remove(job_id)
                    self._abort_queued(entry)
                    return self._view_locked(entry)
                backend = entry.backend
                meta = Meta(request_id=entry.record.request_id, job_id=job_id)
                view = self._view_locked(entry)
            else:
                backend, meta, view = None, None, None
        if view is None:
            return self._known_view(job_id) if entry is None else self._final_view(entry)
        if backend is not None and meta is not None:
            self._cancel_backend(backend, meta)
        return view

    # --- the worker thread -------------------------------------------------------------

    def run_next(self) -> bool:
        """Run the oldest PLANNED job to its end; False when there is none (or one is running)."""
        with self._cond:
            if self._running is not None or not self._queue:
                return False
            job_id = self._queue.popleft()
            self._running = job_id
            entry = self._entries[job_id]
        try:
            self._run(JobHandle(entry, self._cond, self._log))
        finally:
            with self._cond:
                self._running = None
                entry.backend = None
                self._cond.notify_all()
        return True

    def wait_for_work(self, timeout_s: float) -> bool:
        """Wait (through the clock) until a job is queued; True when one is."""
        with self._cond:
            if not self._queue:
                self._clock.wait(self._cond, timeout_s)
            return bool(self._queue)

    # --- start-up recovery (13.2.3) ----------------------------------------------------

    def recover_all(self) -> tuple[RecoveryResult, ...]:
        """Steps 1, 3 and 4 and the clean-up over every known store; call before the first
        submit. A store not listed is recovered when it is first opened (13.2.3, J18)."""
        for skipped in self._stores.open_known():
            self._log.emit("store.skipped", "warning", store=skipped)
        return tuple(self._recover_store(store, root) for store, root in self._stores.entries())

    def clean_up_all(self) -> None:
        """The daily clean-up (13.2.4) over every open store; the caller schedules it."""
        for store, root in self._stores.entries():
            self._clean_up(store, root)

    def reconcile_pending(self) -> bool:
        """True when a recovery left operations whose outcome ``reconcile`` can still learn."""
        with self._cond:
            return any(result.pending_operation_ids for _, result in self._recovered)

    def reconcile(self, backend: Backend) -> tuple[str, ...]:
        """Step 2: record the operations the add-in completed that the journal never saw."""
        with self._cond:
            found = self._recovered
        completed = backend.completed_operations()
        recorded: list[str] = []
        for store, result in found:
            recorded.extend(record_completed_operations(store, result, completed))
        with self._cond:
            self._recovered = tuple(item for item in self._recovered if item not in found)
        return tuple(recorded)

    # --- internals ---------------------------------------------------------------------

    def _read_fingerprint(self, path: str) -> str | None:
        try:
            data = self._stores.fs.read_bytes(path)
            return f"sha256:{hashlib.sha256(data).hexdigest()}"
        except (FileNotFoundError, OSError):
            return None

    def _recover_store(self, store: Store, project_root: str) -> RecoveryResult:
        result = recover(store, self._clock, self._read_fingerprint)
        with self._cond:
            self._recovered = (*self._recovered, (store, result))
        for job in result.interrupted:
            self._log.emit("job.interrupted", "warning", job_id=job.job_id)
        self._clean_up(store, project_root)
        return result

    def _clean_up(self, store: Store, project_root: str) -> None:
        done = clean_up(store, self._clock, self._settings_for(project_root))
        if done.error is not None:
            self._log.emit("store.clean_up_skipped", "warning", error_code=done.error.code)

    def _wait_locked(self, entry: JobEntry, deadline: float) -> tuple[JobView, bool]:
        initial = entry.record.state
        while not entry.record.is_final and entry.record.state == initial:
            remaining = deadline - self._clock.monotonic_s()
            if remaining <= 0:
                break
            self._clock.wait(self._cond, remaining)
        return self._view_locked(entry), entry.record.state != initial

    def _run(self, handle: JobHandle) -> None:
        try:
            settings = self._settings_for(handle.record.project_root)
            ctx = RunContext(
                handle,
                self._provider,
                self._ids,
                self._log,
                settings,
                self._mappings_for(settings),
            )
            outcome = run(ctx)
            self._log.emit(
                "job.finished",
                "info",
                job_id=handle.record.job_id,
                state=outcome.state,
                error_code=outcome.error_code,
            )
        except Exception as error:
            self._fail_unexpected(handle, error)

    def _fail_unexpected(self, handle: JobHandle, error: Exception) -> None:
        job_id = handle.record.job_id
        self._log.emit("job.error", "error", job_id=job_id, reason=type(error).__name__)
        if not handle.record.is_final:
            body = error_object(
                ErrorCode.EXEC_INTERRUPTED.value, "The job stopped on an unexpected error."
            )
            handle.advance("FAILED", "unexpected error", body)

    def _abort_queued(self, entry: JobEntry) -> None:
        body = error_object(
            ErrorCode.EXEC_CANCELLED.value, "The job was cancelled before it started."
        )
        JobHandle(entry, self._cond, self._log).advance_locked("ABORTED", "cancelled", body)

    def _cancel_backend(self, backend: Backend, meta: Meta) -> None:
        try:
            backend.cancel(meta=meta)
        except Exception as error:
            name = type(error).__name__
            self._log.emit("job.cancel_failed", "warning", job_id=meta.job_id, reason=name)

    def _view_locked(self, entry: JobEntry) -> JobView:
        return JobView(entry.record, self._position_locked(entry))

    def _final_view(self, entry: JobEntry) -> JobView:
        with self._cond:
            return self._view_locked(entry)

    def _position_locked(self, entry: JobEntry) -> int | None:
        job_id = entry.record.job_id
        if entry.record.state != "PLANNED":
            return None
        if job_id == self._running:
            return 0
        ahead = 0 if self._running is None else 1
        return ahead + list(self._queue).index(job_id)

    def _stored_view(self, job_id: str) -> JobView | None:
        store = self._stores.store_of_job(job_id)
        record = None if store is None else store.get_job(job_id)
        return JobView(record, None) if isinstance(record, JobRecord) else None

    def _known_view(self, job_id: str) -> JobView:
        view = self._stored_view(job_id)
        if view is None:
            raise UnknownJobError(job_id)
        return view
