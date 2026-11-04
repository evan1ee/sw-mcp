"""Job engine types: the check_drawing spec, the read-only job view and internal errors."""

from dataclasses import dataclass

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.error_codes import DEFAULT_RETRYABLE, ErrorCode

from cad_application.paths import Authorized
from cad_application.store.job_records import JobRecord, JobState


@dataclass(frozen=True, slots=True)
class CheckDrawingSpec:
    """What ``check_drawing`` asks for, after the path checks and the fingerprint (8.4)."""

    authorized: Authorized
    fingerprint: str
    sheets: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class JobView:
    """An immutable copy of a job's state; nothing outside the engine sees mutable state."""

    record: JobRecord
    queued_position: int | None

    @property
    def job_id(self) -> str:
        return self.record.job_id

    @property
    def state(self) -> JobState:
        return self.record.state


@dataclass(frozen=True, slots=True)
class Outcome:
    """How a job run ended: its final state and, for FAILED and ABORTED, the error code."""

    state: JobState
    error_code: str | None = None


class UnknownJobError(KeyError):
    """No job with this ID is known to the engine."""


def error_object(code: str, message: str, details: JsonValue = None) -> dict[str, JsonValue]:
    """The ADR-037 error object stored on a job. Unknown codes are never retryable."""
    try:
        retryable = DEFAULT_RETRYABLE[ErrorCode(code)]
    except ValueError:
        retryable = "never"
    body: dict[str, JsonValue] = {"code": code, "message": message, "retryable": retryable}
    if details is not None:
        body["details"] = details
    return body


class JobStop(Exception):  # noqa: N818 - control flow that ends a job, not an error to report
    """Ends a job run: a failure with a catalogue code, or a cancellation."""

    def __init__(self, code: str, message: str, details: JsonValue = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details

    @property
    def cancelled(self) -> bool:
        return self.code == ErrorCode.EXEC_CANCELLED.value

    def error(self) -> dict[str, JsonValue]:
        return error_object(self.code, self.message, self.details)


def new_job_record(
    job_id: str, request_id: str, spec: CheckDrawingSpec, created_at: str
) -> JobRecord:
    """The PLANNED record of a ``check_drawing`` job (13.2.1)."""
    arguments: dict[str, JsonValue] = {"path": spec.authorized.path}
    if spec.sheets is not None:
        arguments["sheets"] = list(spec.sheets)
    return JobRecord(
        job_id=job_id,
        job_type="check_drawing",
        state="PLANNED",
        created_at=created_at,
        started_at=None,
        ended_at=None,
        request_id=request_id,
        arguments=arguments,
        project_root=spec.authorized.project_root,
        drawing_id=None,
        fingerprint=spec.fingerprint,
        progress=None,
        snapshot_id=None,
        report_id=None,
        error=None,
        warnings=(),
        documents=(),
        next_op_seq=1,
    )
