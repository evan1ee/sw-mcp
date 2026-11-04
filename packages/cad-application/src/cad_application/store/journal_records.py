"""Journal records (spec 13.2.3): one JSON object per line of ``journal.jsonl``."""

from dataclasses import dataclass
from typing import Literal

from cad_ir.core.json_types import JsonValue

from cad_application.store.codec import (
    Obj,
    get_bool,
    get_int,
    get_list,
    get_opt_str,
    get_str,
)
from cad_application.store.job_records import JobState, parse_state

type DocumentAction = Literal["open", "save", "close"]


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


type JournalRecord = (
    StateRecord | BatchSentRecord | OpResultRecord | SnapshotRecord | DocumentRecord | NoteRecord
)


def _action(text: str) -> DocumentAction:
    if text == "save":
        return "save"
    return "close" if text == "close" else "open"


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
    if kind == "state":
        return _state_record(obj, ts, job_id)
    if kind == "batch_sent":
        return BatchSentRecord(
            ts,
            job_id,
            get_int(obj, "batch_seq"),
            _strings(obj, "operation_ids"),
            _strings(obj, "documents"),
        )
    if kind == "op_result":
        return OpResultRecord(
            ts,
            job_id,
            get_str(obj, "operation_id"),
            get_bool(obj, "ok"),
            get_opt_str(obj, "error_code"),
            obj.get("recovered") is True,
        )
    if kind == "snapshot":
        return SnapshotRecord(ts, job_id, get_str(obj, "snapshot_id"), get_opt_str(obj, "sheet"))
    if kind == "document":
        path, owned = get_str(obj, "path"), get_bool(obj, "owned")
        return DocumentRecord(ts, job_id, path, _action(get_str(obj, "action")), owned)
    return NoteRecord(ts, job_id, get_str(obj, "message"))
