"""Ports the application depends on (guideline G2). Adapters live in other packages.

Backend errors: ``cad_application`` cannot import ``cad_protocol.errors.IpcError``. The job runner
treats any exception with a string ``code`` attribute as a backend error, described by the
``CodedError`` protocol (``IpcError`` has one). ``BackendCallError`` is this package's own
exception of that shape, used by test doubles and adapters that have no IPC type.
"""

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import HelloResult, Meta, OperationGroup, OpsApplyResult

from cad_application.ids import IdPrefix
from cad_application.store.errors import StoreError
from cad_application.store.job_records import JobRecord
from cad_application.store.journal_records import JournalRecord
from cad_application.store.records import DrawingMatch, DrawingRecord, PartRecord, ReportMeta

type LogValue = str | int | None


class CodedError(Protocol):
    """What the job runner reads from a backend exception (ADR-037 shape)."""

    code: str
    message: str
    details: JsonValue


class BackendCallError(Exception):
    """A backend call failed with a catalogue code."""

    def __init__(self, code: str, message: str, details: JsonValue = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


class BackendUnavailable(Exception):  # noqa: N818 - reads as a state, like the port name
    """``BackendProvider.acquire`` found no usable session: ``BACKEND_LOST`` or
    ``BACKEND_SESSION_AMBIGUOUS`` (8.6.1)."""

    def __init__(self, code: str, message: str, details: JsonValue = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


class Backend(Protocol):
    """A CAD backend session (ADR-036): the add-in, or a replay of one."""

    @property
    def session(self) -> HelloResult: ...

    def snapshot_drawing(
        self, document: str, sheets: Sequence[str] | None = None, *, meta: Meta | None = None
    ) -> JsonValue: ...

    def measure_part(self, document: str, *, meta: Meta | None = None) -> JsonValue: ...

    def apply_ops(
        self, groups: Sequence[OperationGroup], *, meta: Meta | None = None
    ) -> OpsApplyResult: ...

    def completed_operations(self) -> tuple[str, ...]: ...

    def cancel(self, *, meta: Meta | None = None) -> bool: ...

    def close(self) -> None: ...


class BackendProvider(Protocol):
    """Connects to the SOLIDWORKS session (8.6.1).

    Raises ``BackendUnavailable`` (or any exception with ``code`` ``BACKEND_LOST`` or
    ``BACKEND_SESSION_AMBIGUOUS``). Notifications of the session reach ``on_notification`` with
    the method name and its params.
    """

    def acquire(self, on_notification: Callable[[str, JsonValue], None]) -> Backend: ...


class Clock(Protocol):
    """Time and waiting (ADR-053), injectable for determinism tests."""

    def now(self) -> datetime:
        """The current time, timezone-aware UTC."""
        ...

    def monotonic_s(self) -> float: ...

    def wait(self, cond: threading.Condition, timeout_s: float) -> None:
        """Wait on ``cond`` for at most ``timeout_s``; the caller holds ``cond``."""
        ...


class IdSource(Protocol):
    """Makes ``<prefix>_<ULID>`` IDs (13.2.1)."""

    def new_id(self, prefix: IdPrefix) -> str: ...


@dataclass(frozen=True, slots=True)
class FileStat:
    is_dir: bool
    size: int
    mtime_ns: int


class LockHeld(Exception):  # noqa: N818 - named after the state it reports
    """The exclusive lock is already held."""


class Lock(Protocol):
    def release(self) -> None: ...


class FileSystem(Protocol):
    """All file effects (G2). Paths are absolute Windows paths as ``str``."""

    def resolve(self, path: str) -> str:
        """Absolute, normalized, links and junctions followed.

        Raises ``FileNotFoundError`` only when a parent folder is missing.
        """
        ...

    def stat(self, path: str) -> FileStat | None: ...

    def read_bytes(self, path: str) -> bytes: ...

    def list_dir(self, path: str) -> tuple[str, ...]:
        """Entry names, sorted."""
        ...

    def make_dirs(self, path: str) -> None: ...

    def write_atomic(self, path: str, data: bytes) -> None:
        """Temporary file, flush, ``fsync``, rename over the target (13.2.2)."""
        ...

    def write_new(self, path: str, data: bytes) -> None:
        """Like ``write_atomic``, but raises ``FileExistsError`` if the target exists."""
        ...

    def rename_new(self, source: str, target: str) -> None:
        """Atomically rename source to target without replacing target.

        Raises FileExistsError if target exists.
        """
        ...

    def append_line(self, path: str, line: str) -> None:
        """Append ``line`` and ``\\n``, flushed and ``fsync``ed before returning."""
        ...

    def remove(self, path: str) -> None:
        """Delete a file or an empty folder."""
        ...

    def lock_exclusive(self, path: str) -> Lock:
        """Take a non-blocking exclusive lock; raises ``LockHeld``."""
        ...


class EventLog(Protocol):
    """Structured events (G3). The sink decides which fields reach the file."""

    def emit(self, event: str, level: str, **fields: LogValue) -> None: ...


class Store(Protocol):
    """The project store (13.2). ``FileStore`` is the one implementation (G2): over the
    ``MemoryFileSystem`` it is the fake. Methods return ``StoreError`` for a corrupt record.
    """

    def find_drawing(self, path: str, fingerprint: str) -> DrawingRecord | None: ...

    def match_drawing(self, path: str, fingerprint: str) -> DrawingMatch: ...

    def get_drawing(self, drawing_id: str) -> DrawingRecord | StoreError | None: ...

    def put_drawing(self, record: DrawingRecord) -> None: ...

    def put_snapshot(self, drawing_id: str, snapshot_id: str, doc: JsonValue) -> None:
        """Write once; raises ``FileExistsError`` if the snapshot exists."""
        ...

    def get_snapshot(self, drawing_id: str, snapshot_id: str) -> JsonValue | StoreError | None: ...

    def put_report(self, report_id: str, report: JsonValue, meta: ReportMeta) -> None:
        """Meta first, then the report, both written once (``FileExistsError`` if present)."""
        ...

    def get_report(self, report_id: str) -> tuple[JsonValue, ReportMeta] | StoreError | None: ...

    def has_job(self, job_id: str) -> bool: ...

    def has_report(self, report_id: str) -> bool: ...

    def timestamp(self) -> str:
        """Now as a store timestamp (UTC ISO 8601, milliseconds), from the store's ``Clock``."""
        ...

    # Jobs and the journal (13.2.2, 13.2.3).

    def create_job(self, record: JobRecord) -> None:
        """The first ``state`` record, then ``job.json``."""
        ...

    def append(self, job_id: str, record: JournalRecord) -> None:
        """One journal line, flushed and ``fsync``ed before returning."""
        ...

    def put_job(self, record: JobRecord) -> None: ...

    def get_job(self, job_id: str) -> JobRecord | StoreError | None: ...

    def list_job_ids(self) -> tuple[str, ...]: ...

    def list_jobs(self) -> tuple[JobRecord, ...] | StoreError: ...

    def read_journal(self, job_id: str) -> tuple[JournalRecord, ...] | StoreError:
        """A torn last line is ignored; any other unreadable line is ``STORE_CORRUPT``."""
        ...

    # Listing and deleting, for clean-up (13.2.4).

    def list_drawings(self) -> tuple[DrawingRecord, ...] | StoreError: ...

    def list_snapshot_ids(self, drawing_id: str) -> tuple[str, ...]:
        """Sorted ascending: ULIDs sort by time."""
        ...

    def delete_snapshot(self, drawing_id: str, snapshot_id: str) -> None: ...

    def list_report_metas(self) -> tuple[ReportMeta, ...] | StoreError: ...

    def delete_report(self, report_id: str) -> None: ...

    def put_plan(self, plan_hash: str, plan: JsonValue) -> bool: ...

    def put_part_revision(
        self, ref: str, doc: JsonValue, expected_revision: int | None
    ) -> str | StoreError: ...

    def get_part_revision(self, ref: str) -> JsonValue | StoreError | None: ...

    def put_part_record(self, record: PartRecord) -> None: ...

    def get_part_record(self, part_key: str) -> PartRecord | StoreError | None: ...

    def delete_job(self, job_id: str) -> None: ...

    def close(self) -> None: ...
