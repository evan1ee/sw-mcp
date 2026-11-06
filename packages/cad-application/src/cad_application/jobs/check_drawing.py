"""The ``check_drawing`` job (spec 8.4): open read-only, read back, check, store, close.

Backend errors are read through their ``code`` attribute (see ``ports``), so this module never
imports an IPC type. ``JobStop`` carries a failure or a cancellation out of any step; ``_stopped``
turns it into the final state after closing the drawing the job owns.
"""

import ntpath
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Final, cast

from cad_drawing.checks import TitleBlockMapping, build_report, parse_snapshot
from cad_drawing.checks.report import DrawingReport
from cad_ir.core import CanonicalizationError, IssueReport, content_hash
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.error_codes import ErrorCode
from cad_ir.generated.ipc import HelloResult, Meta, Operation, OperationGroup

from cad_application.config.settings import Settings
from cad_application.jobs.handle import JobHandle
from cad_application.jobs.model import JobStop, Outcome
from cad_application.ports import Backend, BackendProvider, EventLog, IdSource
from cad_application.store.job_records import JobDocument
from cad_application.store.journal_records import (
    BatchSentRecord,
    DocumentRecord,
    OpResultRecord,
    SnapshotRecord,
)
from cad_application.store.records import DrawingRecord, JobWarning, ReportMeta

_STEPS: Final = 4
_CAPABILITIES: Final = ("drawing.snapshot", "ops.apply")
_OPERATIONS: Final = ("document.open", "document.close")
# After these the add-in may not answer, or the user is working in the document: never send
# a close (8.3 rule 12, rule 13).
_NO_CLOSE: Final = frozenset(
    {
        ErrorCode.BACKEND_LOST.value,
        ErrorCode.BACKEND_UI_BLOCKED.value,
        ErrorCode.EXEC_TIMEOUT.value,
        ErrorCode.EXEC_INTERRUPTED_BY_USER.value,
    }
)


@dataclass(frozen=True, slots=True)
class RunContext:
    handle: JobHandle
    provider: BackendProvider
    ids: IdSource
    log: EventLog
    settings: Settings
    mappings: Mapping[str, TitleBlockMapping]


def run(ctx: RunContext) -> Outcome:
    """Run the job to a final state; every state change goes through ``ctx.handle``."""
    return _Run(ctx).execute()


def _stop_from(error: Exception) -> JobStop | None:
    """A ``JobStop`` for an exception with a string ``code``; None for any other exception."""
    code = getattr(error, "code", None)
    if not isinstance(code, str):
        return None
    message = getattr(error, "message", None)
    details = getattr(error, "details", None)
    text = message if isinstance(message, str) else "The backend call failed."
    return JobStop(code, text, cast("JsonValue", details))


class _Run:
    def __init__(self, ctx: RunContext) -> None:
        self._ctx = ctx
        self._h = ctx.handle
        self._path = ctx.handle.spec.authorized.path
        self._backend: Backend | None = None
        self._touched = False  # an open batch was sent
        self._open = False
        self._owned = False
        self._batches = 0
        self._drawing: DrawingRecord | None = None

    def execute(self) -> Outcome:
        try:
            backend = self._validate()
            self._open_drawing(backend)
            doc = self._read_back(backend)
            self._store_snapshot(doc)
            self._verify_and_commit(doc)
        except JobStop as stop:
            return self._stopped(stop)
        except Exception:
            self._close_drawing()  # the engine fails the job; the drawing must not stay open
            raise
        return Outcome("COMMITTED")

    # --- PLANNED -> VALIDATED ----------------------------------------------------------

    def _validate(self) -> Backend:
        try:
            backend = self._ctx.provider.acquire(self._h.on_notification)
        except Exception as error:
            stop = _stop_from(error)
            if stop is None:
                raise
            raise stop from error
        self._backend = backend
        self._h.set_backend(backend)
        self._note_session_warnings(backend.session)
        self._checkpoint()
        self._require_capabilities(backend.session)
        self._h.advance("VALIDATED", "backend acquired; capabilities present")
        return backend

    def _note_session_warnings(self, session: HelloResult) -> None:
        found = tuple(JobWarning("solidworks_version_warning", w) for w in session.warnings)
        if found:
            self._h.edit(lambda r: replace(r, warnings=(*r.warnings, *found)))

    def _require_capabilities(self, session: HelloResult) -> None:
        operations = {o.op for o in session.operations}
        missing = [c for c in _CAPABILITIES if c not in session.capabilities]
        missing += [op for op in _OPERATIONS if op not in operations]
        if missing:
            raise JobStop(
                ErrorCode.BACKEND_CAPABILITY_MISSING.value,
                "The SOLIDWORKS add-in lacks a capability this job needs.",
                {"missing": cast("list[JsonValue]", missing)},
            )

    # --- EXECUTING ---------------------------------------------------------------------

    def _open_drawing(self, backend: Backend) -> None:
        self._checkpoint()
        self._h.advance("EXECUTING", "opening the drawing")
        self._h.progress(1, _STEPS, "opening the drawing")
        params: JsonValue = {"path": self._path, "read_only": True, "fully_resolved": True}
        result = self._send(backend, "document.open", params, check=True)
        self._owned = isinstance(result, dict) and result.get("owned") is True
        self._open = True
        record = DocumentRecord(
            self._h.timestamp(), self._h.record.job_id, self._path, "open", self._owned
        )
        self._h.append(record)
        document = JobDocument(self._path, self._owned, "known")
        self._h.edit(lambda r: replace(r, documents=(document,)))

    def _read_back(self, backend: Backend) -> JsonValue:
        self._checkpoint()
        self._h.progress(2, _STEPS, "reading the drawing back")
        record, sheets = self._h.record, self._h.spec.sheets
        meta = Meta(request_id=record.request_id, job_id=record.job_id)
        doc = self._call(lambda: backend.snapshot_drawing(self._path, sheets, meta=meta))
        self._checkpoint()
        return doc

    @classmethod
    def _validate_snapshot(cls, doc: JsonValue) -> None:
        """Schema, rules and canonical form, before anything is written (13.2.3)."""
        try:  # first: parse_snapshot assumes numbers that canonicalize
            content_hash(doc)
        except CanonicalizationError as error:
            raise JobStop(
                ErrorCode.IR_RULE_VIOLATED.value,
                "The add-in returned a snapshot with a number that cannot be canonicalized.",
            ) from error
        parsed = parse_snapshot(doc)
        if isinstance(parsed, IssueReport):
            raise cls._invalid_snapshot(parsed)

    def _store_snapshot(self, doc: JsonValue) -> None:
        self._validate_snapshot(doc)
        h, store, ids = self._h, self._h.store, self._ctx.ids
        fingerprint = h.spec.fingerprint
        match = self._store_io(lambda: store.match_drawing(self._path, fingerprint))
        drawing = match.record or DrawingRecord(
            drawing_id=ids.new_id("drw"),
            path=self._path,
            fingerprint=fingerprint,
            produced=False,
            drawing_intent=None,
            latest_snapshot_id=None,
            latest_report_id=None,
            updated_at=h.timestamp(),
        )
        snapshot_id = ids.new_id("snap")
        self._store_io(lambda: store.put_snapshot(drawing.drawing_id, snapshot_id, doc))
        h.append(SnapshotRecord(h.timestamp(), h.record.job_id, snapshot_id, None))
        extra = () if match.warning is None else (match.warning,)
        h.edit(
            lambda r: replace(
                r,
                drawing_id=drawing.drawing_id,
                snapshot_id=snapshot_id,
                warnings=(*r.warnings, *extra),
            )
        )
        self._drawing = drawing

    # --- VERIFYING ---------------------------------------------------------------------

    def _verify_and_commit(self, doc: JsonValue) -> None:
        h, ctx = self._h, self._ctx
        h.advance("VERIFYING", "checking the drawing")
        h.progress(3, _STEPS, "checking the drawing")
        report = build_report(
            doc,
            thresholds=ctx.settings.check_thresholds(),
            title_block_mappings=ctx.mappings,
        )
        if isinstance(report, IssueReport):
            raise self._invalid_snapshot(report)
        self._checkpoint()  # the last place to cancel: the report write ends COMMITTED
        h.progress(4, _STEPS, "storing the report")
        self._write_report(report)
        self._close_drawing()
        h.advance("COMMITTED", "report stored")

    @staticmethod
    def _invalid_snapshot(report: IssueReport) -> JobStop:
        code = report.issues[0].code.value if report.issues else ErrorCode.IR_SCHEMA_INVALID.value
        return JobStop(
            code,
            "The add-in returned a snapshot that failed validation.",
            {"issue_count": len(report.issues) + report.omitted},
        )

    def _write_report(self, report: DrawingReport) -> None:
        h, store = self._h, self._h.store
        drawing = self._drawing
        assert drawing is not None
        record = h.record
        assert record.snapshot_id is not None
        report_id = self._ctx.ids.new_id("rep")
        meta = ReportMeta(
            report_id,
            record.job_id,
            drawing.drawing_id,
            record.snapshot_id,
            h.timestamp(),
            record.warnings,
        )
        updated = replace(
            drawing,
            latest_snapshot_id=record.snapshot_id,
            latest_report_id=report_id,
            updated_at=h.timestamp(),
        )
        self._store_io(lambda: store.put_report(report_id, report.to_json(), meta))
        self._store_io(lambda: store.put_drawing(updated))
        h.edit(lambda r: replace(r, report_id=report_id))

    # --- ending ------------------------------------------------------------------------

    def _stopped(self, stop: JobStop) -> Outcome:
        if stop.code in _NO_CLOSE:
            self._mark_documents_unknown()
        else:
            self._close_drawing()
        if stop.cancelled:
            self._h.advance("ABORTED", "cancelled", stop.error())
            return Outcome("ABORTED", stop.code)
        self._h.advance("FAILED", stop.message, stop.error())
        return Outcome("FAILED", stop.code)

    def _mark_documents_unknown(self) -> None:
        if self._touched:
            document = JobDocument(self._path, self._owned, "unknown")
            self._h.edit(lambda r: replace(r, documents=(document,)))

    def _close_drawing(self) -> None:
        """Close the drawing the job owns; a failure is a warning, never a different outcome."""
        backend = self._backend
        if backend is None or not (self._open and self._owned):
            return
        try:
            self._send(backend, "document.close", {"path": self._path}, check=False)
        except Exception as error:
            self._close_failed(error)
            return
        self._open = False
        h = self._h
        h.append(DocumentRecord(h.timestamp(), h.record.job_id, self._path, "close", True))
        h.edit(lambda r: replace(r, documents=()))

    def _close_failed(self, error: Exception) -> None:
        name = type(error).__name__
        self._ctx.log.emit("job.close_failed", "warning", job_id=self._h.record.job_id, reason=name)
        warning = JobWarning(
            "drawing_close_failed", "The job could not close the drawing it opened."
        )
        unknown = JobDocument(self._path, self._owned, "unknown")
        self._h.edit(lambda r: replace(r, warnings=(*r.warnings, warning), documents=(unknown,)))

    # --- helpers -----------------------------------------------------------------------

    @staticmethod
    def _store_io[T](call: Callable[[], T]) -> T:
        """A store file that cannot be written fails the job with ``STORE_UNAVAILABLE`` (13.2.2)."""
        try:
            return call()
        except OSError as error:
            raise JobStop(
                ErrorCode.STORE_UNAVAILABLE.value,
                "A project store file cannot be read or written.",
                {"reason": "io_error"},
            ) from error

    def _checkpoint(self) -> None:
        if self._h.cancel_requested:
            raise JobStop(ErrorCode.EXEC_CANCELLED.value, "The job was cancelled.")

    def _send(self, backend: Backend, op: str, params: JsonValue, *, check: bool) -> JsonValue:
        """One operation as its own batch: ``batch_sent`` is on disk before ``apply_ops``."""
        h = self._h
        record = h.record
        op_id = f"{record.job_id}:{record.next_op_seq}"
        self._batches += 1
        batch = BatchSentRecord(
            h.timestamp(), record.job_id, self._batches, (op_id,), (self._path,)
        )
        h.append(batch)
        h.edit(lambda r: replace(r, next_op_seq=r.next_op_seq + 1))
        self._touched = self._touched or op == "document.open"
        operation = Operation(operation_id=op_id, op=op, params=params)
        groups = (OperationGroup(document=self._path, operations=(operation,)),)
        meta = Meta(request_id=record.request_id, job_id=record.job_id, operation_id=op_id)
        applied = self._call(lambda: backend.apply_ops(groups, meta=meta), check=check)
        outcome = next((o for o in applied.outcomes if o.operation_id == op_id), None)
        if outcome is None:
            raise JobStop(
                ErrorCode.EXEC_INTERRUPTED.value, "The add-in did not answer the operation."
            )
        error = outcome.error
        h.append(
            OpResultRecord(h.timestamp(), record.job_id, op_id, error is None, error and error.code)
        )
        if error is not None:
            raise JobStop(error.code, error.message, error.details)
        return outcome.result

    def _call[T](self, call: Callable[[], T], *, check: bool = True) -> T:
        """Run a backend call; afterwards a notification may discard its result (8.4)."""
        try:
            value = call()
        except Exception as error:
            stop = _stop_from(error)
            if stop is None:
                raise
            raise stop from error
        if check:
            self._check_notifications()
        return value

    def _check_notifications(self) -> None:
        for method, params in self._h.take_notifications():
            if method == "session.ui_blocked":
                raise JobStop(
                    ErrorCode.BACKEND_UI_BLOCKED.value,
                    "SOLIDWORKS stopped responding to the add-in.",
                )
            if method == "document.event" and self._foreign_event(params):
                raise JobStop(
                    ErrorCode.EXEC_INTERRUPTED_BY_USER.value,
                    "The drawing was changed in SOLIDWORKS while the job was using it.",
                )

    def _foreign_event(self, params: JsonValue) -> bool:
        """An event on the job's drawing that does not carry this job's ID in ``_meta``."""
        if not isinstance(params, dict):
            return False
        document = params.get("document")
        if not isinstance(document, str) or ntpath.normcase(document) != ntpath.normcase(
            self._path
        ):
            return False
        meta = params.get("_meta")
        own = isinstance(meta, dict) and meta.get("job_id") == self._h.record.job_id
        return not own
