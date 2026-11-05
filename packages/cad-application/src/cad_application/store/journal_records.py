"""Journal records (spec 13.2.3): one JSON object per line of ``journal.jsonl``."""

from dataclasses import dataclass
from typing import Literal

from cad_ir.core.json_types import JsonValue

from cad_application.store.codec import (
    Obj,
    as_obj,
    get_bool,
    get_int,
    get_list,
    get_opt_str,
    get_str,
)
from cad_application.store.job_records import JobState, parse_state

type DocumentAction = Literal["open", "create", "save", "close"]


def _strings(obj: Obj, key: str) -> tuple[str, ...]:
    return tuple(item for item in get_list(obj, key) if isinstance(item, str))


@dataclass(frozen=True, slots=True)
class StateRecord:
    ts: str
    job_id: str
    from_state: JobState | None
    to: JobState
    reason: str
    error: Obj | None = None

    def to_json(self) -> Obj:
        return {
            "type": "state",
            "ts": self.ts,
            "job_id": self.job_id,
            "from": self.from_state,
            "to": self.to,
            "reason": self.reason,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class BatchSentRecord:
    ts: str
    job_id: str
    batch_seq: int
    operation_ids: tuple[str, ...]
    documents: tuple[str, ...]

    def to_json(self) -> Obj:
        ops: list[JsonValue] = list(self.operation_ids)
        docs: list[JsonValue] = list(self.documents)
        return {
            "type": "batch_sent",
            "ts": self.ts,
            "job_id": self.job_id,
            "batch_seq": self.batch_seq,
            "operation_ids": ops,
            "documents": docs,
        }


@dataclass(frozen=True, slots=True)
class OpResultRecord:
    ts: str
    job_id: str
    operation_id: str
    ok: bool
    error_code: str | None
    recovered: bool = False

    def to_json(self) -> Obj:
        body: Obj = {
            "type": "op_result",
            "ts": self.ts,
            "job_id": self.job_id,
            "operation_id": self.operation_id,
            "ok": self.ok,
            "error_code": self.error_code,
        }
        return body | {"recovered": True} if self.recovered else body


@dataclass(frozen=True, slots=True)
class OpVerifiedRecord:
    ts: str
    job_id: str
    operation_id: str
    node: str | None
    feature_id: str | None
    observation: Obj | None
    checks: tuple[Obj, ...] | list[Obj]
    status: str

    def to_json(self) -> Obj:
        return {
            "type": "op_verified",
            "ts": self.ts,
            "job_id": self.job_id,
            "operation_id": self.operation_id,
            "node": self.node,
            "feature_id": self.feature_id,
            "observation": self.observation,
            "checks": list(self.checks),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    ts: str
    job_id: str
    snapshot_id: str
    sheet: str | None

    def to_json(self) -> Obj:
        return {
            "type": "snapshot",
            "ts": self.ts,
            "job_id": self.job_id,
            "snapshot_id": self.snapshot_id,
            "sheet": self.sheet,
        }


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    ts: str
    job_id: str
    path: str
    action: DocumentAction
    owned: bool

    def to_json(self) -> Obj:
        return {
            "type": "document",
            "ts": self.ts,
            "job_id": self.job_id,
            "path": self.path,
            "action": self.action,
            "owned": self.owned,
        }


@dataclass(frozen=True, slots=True)
class NoteRecord:
    ts: str
    job_id: str
    message: str

    def to_json(self) -> Obj:
        return {"type": "note", "ts": self.ts, "job_id": self.job_id, "message": self.message}


@dataclass(frozen=True, slots=True)
class PublishIntentRecord:
    ts: str
    job_id: str
    path: str
    fingerprint: str

    def to_json(self) -> Obj:
        return {
            "type": "publish_intent",
            "ts": self.ts,
            "job_id": self.job_id,
            "path": self.path,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class PublishedRecord:
    ts: str
    job_id: str
    path: str
    fingerprint: str | None = None

    def to_json(self) -> Obj:
        body: Obj = {
            "type": "published",
            "ts": self.ts,
            "job_id": self.job_id,
            "path": self.path,
        }
        if self.fingerprint is not None:
            body["fingerprint"] = self.fingerprint
        return body


type JournalRecord = (
    StateRecord
    | BatchSentRecord
    | OpResultRecord
    | OpVerifiedRecord
    | SnapshotRecord
    | DocumentRecord
    | NoteRecord
    | PublishIntentRecord
    | PublishedRecord
)


def _action(text: str) -> DocumentAction:
    if text in ("open", "create", "save", "close"):
        return text  # type: ignore[return-value]
    raise ValueError(f"Unknown document action: {text!r}")


def _state_record(obj: Obj, ts: str, job_id: str) -> StateRecord:
    before = get_opt_str(obj, "from")
    error = obj.get("error")
    return StateRecord(
        ts,
        job_id,
        None if before is None else parse_state(before),
        parse_state(get_str(obj, "to")),
        get_str(obj, "reason"),
        error if isinstance(error, dict) else None,
    )


def journal_from_json(obj: Obj) -> JournalRecord:
    """``obj`` must satisfy the ``JournalRecord`` schema."""
    kind = get_str(obj, "type")
    ts, job_id = get_str(obj, "ts"), get_str(obj, "job_id")
    match kind:
        case "state":
            record: JournalRecord = _state_record(obj, ts, job_id)
        case "batch_sent":
            record = BatchSentRecord(
                ts,
                job_id,
                get_int(obj, "batch_seq"),
                _strings(obj, "operation_ids"),
                _strings(obj, "documents"),
            )
        case "op_result":
            record = OpResultRecord(
                ts,
                job_id,
                get_str(obj, "operation_id"),
                get_bool(obj, "ok"),
                get_opt_str(obj, "error_code"),
                obj.get("recovered") is True,
            )
        case "op_verified":
            checks = tuple(as_obj(c) for c in get_list(obj, "checks"))
            obs = obj.get("observation")
            record = OpVerifiedRecord(
                ts,
                job_id,
                get_str(obj, "operation_id"),
                get_opt_str(obj, "node"),
                get_opt_str(obj, "feature_id"),
                as_obj(obs) if isinstance(obs, dict) else None,
                checks,
                get_str(obj, "status"),
            )
        case "snapshot":
            record = SnapshotRecord(
                ts, job_id, get_str(obj, "snapshot_id"), get_opt_str(obj, "sheet")
            )
        case "document":
            path, owned = get_str(obj, "path"), get_bool(obj, "owned")
            record = DocumentRecord(ts, job_id, path, _action(get_str(obj, "action")), owned)
        case "publish_intent":
            record = PublishIntentRecord(
                ts,
                job_id,
                get_str(obj, "path"),
                get_str(obj, "fingerprint"),
            )
        case "published":
            record = PublishedRecord(
                ts,
                job_id,
                get_str(obj, "path"),
                get_opt_str(obj, "fingerprint"),
            )
        case "note":
            record = NoteRecord(ts, job_id, get_str(obj, "message"))
        case _:
            raise ValueError(f"Unknown journal record type: {kind!r}")
    return record
