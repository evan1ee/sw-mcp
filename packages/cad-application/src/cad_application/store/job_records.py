"""Job records (spec 13.2.1, ``jobs/<job_id>/job.json``). Frozen; changes make new records."""

from dataclasses import dataclass
from typing import Final, Literal, get_args

from cad_ir.core.json_types import JsonValue

from cad_application.store.codec import (
    Obj,
    as_obj,
    get_bool,
    get_int,
    get_list,
    get_obj,
    get_opt_str,
    get_str,
)
from cad_application.store.records import JobWarning

type JobState = Literal[
    "PLANNED", "VALIDATED", "EXECUTING", "VERIFYING", "COMMITTED", "FAILED", "RECOVERY", "ABORTED"
]
type JobType = Literal["plan", "produce_drawing", "check_drawing"]
type DocumentState = Literal["known", "unknown"]

JOB_STATES: Final[tuple[JobState, ...]] = get_args(JobState.__value__)
JOB_TYPES: Final[tuple[JobType, ...]] = get_args(JobType.__value__)
FINAL_STATES: Final[frozenset[JobState]] = frozenset({"COMMITTED", "FAILED", "ABORTED"})


def parse_state(text: str) -> JobState:
    for state in JOB_STATES:
        if state == text:
            return state
    raise ValueError(text)


def _job_type(text: str) -> JobType:
    for job_type in JOB_TYPES:
        if job_type == text:
            return job_type
    raise ValueError(text)


@dataclass(frozen=True, slots=True)
class JobProgress:
    step: int
    of: int
    message: str

    def to_json(self) -> Obj:
        return {"step": self.step, "of": self.of, "message": self.message}

    @staticmethod
    def from_json(obj: Obj) -> "JobProgress":
        return JobProgress(get_int(obj, "step"), get_int(obj, "of"), get_str(obj, "message"))


@dataclass(frozen=True, slots=True)
class JobDocument:
    path: str
    owned: bool
    state: DocumentState

    def to_json(self) -> Obj:
        return {"path": self.path, "owned": self.owned, "state": self.state}

    @staticmethod
    def from_json(obj: Obj) -> "JobDocument":
        state: DocumentState = "unknown" if get_str(obj, "state") == "unknown" else "known"
        return JobDocument(get_str(obj, "path"), get_bool(obj, "owned"), state)


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: str
    job_type: JobType
    state: JobState
    created_at: str
    started_at: str | None
    ended_at: str | None
    request_id: str
    arguments: Obj
    project_root: str
    drawing_id: str | None
    fingerprint: str | None
    progress: JobProgress | None
    snapshot_id: str | None
    report_id: str | None
    error: Obj | None
    warnings: tuple[JobWarning, ...]
    documents: tuple[JobDocument, ...]
    next_op_seq: int
    part_result: Obj | None = None

    @property
    def is_final(self) -> bool:
        return self.state in FINAL_STATES

    def to_json(self) -> Obj:
        warnings: list[JsonValue] = [w.to_json() for w in self.warnings]
        documents: list[JsonValue] = [d.to_json() for d in self.documents]
        body: Obj = {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "state": self.state,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "request_id": self.request_id,
            "arguments": self.arguments,
            "project_root": self.project_root,
            "drawing_id": self.drawing_id,
            "fingerprint": self.fingerprint,
            "progress": None if self.progress is None else self.progress.to_json(),
            "snapshot_id": self.snapshot_id,
            "report_id": self.report_id,
            "error": self.error,
            "warnings": warnings,
            "documents": documents,
            "next_op_seq": self.next_op_seq,
        }
        if self.part_result is not None:
            body["part_result"] = self.part_result
        return body

    @staticmethod
    def from_json(obj: Obj) -> "JobRecord":
        """``obj`` must satisfy the ``JobRecord`` schema."""
        progress = obj.get("progress")
        error = obj.get("error")
        part_result = obj.get("part_result")
        return JobRecord(
            job_id=get_str(obj, "job_id"),
            job_type=_job_type(get_str(obj, "job_type")),
            state=parse_state(get_str(obj, "state")),
            created_at=get_str(obj, "created_at"),
            started_at=get_opt_str(obj, "started_at"),
            ended_at=get_opt_str(obj, "ended_at"),
            request_id=get_str(obj, "request_id"),
            arguments=get_obj(obj, "arguments"),
            project_root=get_str(obj, "project_root"),
            drawing_id=get_opt_str(obj, "drawing_id"),
            fingerprint=get_opt_str(obj, "fingerprint"),
            progress=None if progress is None else JobProgress.from_json(as_obj(progress)),
            snapshot_id=get_opt_str(obj, "snapshot_id"),
            report_id=get_opt_str(obj, "report_id"),
            error=None if error is None else as_obj(error),
            warnings=tuple(JobWarning.from_json(as_obj(w)) for w in get_list(obj, "warnings")),
            documents=tuple(JobDocument.from_json(as_obj(d)) for d in get_list(obj, "documents")),
            next_op_seq=get_int(obj, "next_op_seq"),
            part_result=None if part_result is None else as_obj(part_result),
        )
