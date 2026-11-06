"""Drawing records and report metadata (spec 13.2.1). Frozen; changes make new records."""

from dataclasses import dataclass

from cad_ir.core.json_types import JsonValue

from cad_application.store.codec import (
    Obj,
    as_obj,
    get_bool,
    get_list,
    get_opt_str,
    get_str,
)


@dataclass(frozen=True, slots=True)
class JobWarning:
    """A warning on a job that is not a fact about the snapshot (8.4)."""

    code: str
    message: str

    def to_json(self) -> Obj:
        return {"code": self.code, "message": self.message}

    @staticmethod
    def from_json(obj: Obj) -> "JobWarning":
        return JobWarning(get_str(obj, "code"), get_str(obj, "message"))


@dataclass(frozen=True, slots=True)
class DrawingRecord:
    drawing_id: str
    path: str
    fingerprint: str
    produced: bool
    drawing_intent: JsonValue
    latest_snapshot_id: str | None
    latest_report_id: str | None
    updated_at: str

    def to_json(self) -> Obj:
        return {
            "drawing_id": self.drawing_id,
            "path": self.path,
            "fingerprint": self.fingerprint,
            "produced": self.produced,
            "drawing_intent": self.drawing_intent,
            "latest_snapshot_id": self.latest_snapshot_id,
            "latest_report_id": self.latest_report_id,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_json(obj: Obj) -> "DrawingRecord":
        return DrawingRecord(
            drawing_id=get_str(obj, "drawing_id"),
            path=get_str(obj, "path"),
            fingerprint=get_str(obj, "fingerprint"),
            produced=get_bool(obj, "produced"),
            drawing_intent=obj.get("drawing_intent"),
            latest_snapshot_id=get_opt_str(obj, "latest_snapshot_id"),
            latest_report_id=get_opt_str(obj, "latest_report_id"),
            updated_at=get_str(obj, "updated_at"),
        )


@dataclass(frozen=True, slots=True)
class ReportMeta:
    report_id: str
    execution_id: str
    drawing_id: str
    snapshot_id: str
    created_at: str
    job_warnings: tuple[JobWarning, ...]

    def to_json(self) -> Obj:
        warnings: list[JsonValue] = [w.to_json() for w in self.job_warnings]
        return {
            "report_id": self.report_id,
            "execution_id": self.execution_id,
            "drawing_id": self.drawing_id,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "job_warnings": warnings,
        }

    @staticmethod
    def from_json(obj: Obj) -> "ReportMeta":
        return ReportMeta(
            report_id=get_str(obj, "report_id"),
            execution_id=get_str(obj, "execution_id"),
            drawing_id=get_str(obj, "drawing_id"),
            snapshot_id=get_str(obj, "snapshot_id"),
            created_at=get_str(obj, "created_at"),
            job_warnings=tuple(
                JobWarning.from_json(as_obj(w)) for w in get_list(obj, "job_warnings")
            ),
        )


@dataclass(frozen=True, slots=True)
class DrawingMatch:
    """Result of matching a drawing (13.2.1). ``record`` is None when a new record is needed;
    otherwise it is the matched record with its path or fingerprint updated (not yet stored)."""

    record: DrawingRecord | None
    warning: JobWarning | None


@dataclass(frozen=True, slots=True)
class PartRecord:
    part_key: str
    path: str
    fingerprint: str
    produced: bool
    graph: str
    job_id: str
    updated_at: str

    def to_json(self) -> Obj:
        return {
            "part_key": self.part_key,
            "path": self.path,
            "fingerprint": self.fingerprint,
            "produced": self.produced,
            "graph": self.graph,
            "job_id": self.job_id,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_json(obj: Obj) -> "PartRecord":
        return PartRecord(
            part_key=get_str(obj, "part_key"),
            path=get_str(obj, "path"),
            fingerprint=get_str(obj, "fingerprint"),
            produced=get_bool(obj, "produced"),
            graph=get_str(obj, "graph"),
            job_id=get_str(obj, "job_id"),
            updated_at=get_str(obj, "updated_at"),
        )
