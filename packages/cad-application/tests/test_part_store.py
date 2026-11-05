"""Part store, revision rules, plan reuse, and journal records (spec 3.4.5, 13.2.1, 13.2.3)."""

import pytest
from cad_application.store.codec import Obj
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord
from cad_application.store.journal import recover
from cad_application.store.journal_records import (
    DocumentRecord,
    _action,  # pyright: ignore[reportPrivateUsage]
    journal_from_json,
)
from cad_application.store.records import PartRecord
from cad_application.testing.builders import new_job, open_store
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_ir.core.json_types import JsonValue

TS = "2026-11-04T09:00:00.000Z"
FP_A = "sha256:" + "a" * 64
FP_B = "sha256:" + "b" * 64


def _env() -> tuple[FileStore, MemoryFileSystem, FakeClock, SequentialIdSource]:
    fs = MemoryFileSystem()
    clock = FakeClock()
    return open_store(fs, clock), fs, clock, SequentialIdSource()


def _restart(fs: MemoryFileSystem, clock: FakeClock) -> FileStore:
    fs.drop_locks()
    return open_store(fs, clock)


def test_action_round_trip() -> None:
    # "create" survives write and read
    rec = DocumentRecord(
        TS, "job_01H1234567890ABCDEFGHJKMNP", "C:\\Work\\part.SLDPRT", "create", True
    )
    json_data = rec.to_json()
    assert json_data["action"] == "create"
    loaded = journal_from_json(json_data)
    assert isinstance(loaded, DocumentRecord)
    assert loaded.action == "create"
    assert loaded.path == "C:\\Work\\part.SLDPRT"
    assert loaded.owned is True

    # _action mapping
    assert _action("create") == "create"
    assert _action("open") == "open"
    assert _action("save") == "save"
    assert _action("close") == "close"

    # unknown action must raise ValueError, NOT fall back to "open"
    with pytest.raises(ValueError, match="Unknown document action"):
        _action("modify")
    with pytest.raises(ValueError, match="Unknown document action"):
        _action("delete")


def test_unknown_documents_include_create() -> None:
    store, fs, clock, ids = _env()
    job = new_job(ids, clock)
    store.create_job(job)

    # Document created and not closed -> state: "unknown"
    store.append(
        job.job_id,
        DocumentRecord(TS, job.job_id, "C:\\Work\\part_working.SLDPRT", "create", True),
    )
    # Another document created and closed -> not unknown
    store.append(
        job.job_id,
        DocumentRecord(TS, job.job_id, "C:\\Work\\temp.SLDPRT", "create", True),
    )
    store.append(
        job.job_id,
        DocumentRecord(TS, job.job_id, "C:\\Work\\temp.SLDPRT", "close", True),
    )

    reopened = _restart(fs, clock)
    recover(reopened, clock)
    saved = reopened.get_job(job.job_id)
    assert isinstance(saved, JobRecord)
    assert [(d.path, d.owned, d.state) for d in saved.documents] == [
        ("C:\\Work\\part_working.SLDPRT", True, "unknown")
    ]


def test_old_job_json_loads() -> None:
    # v0 record without part_result parses cleanly with part_result=None
    v0_payload: Obj = {
        "job_id": "job_01H1234567890ABCDEFGHJKMNP",
        "job_type": "plan",
        "state": "PLANNED",
        "created_at": TS,
        "started_at": None,
        "ended_at": None,
        "request_id": "req_01H1234567890ABCDEFGHJKMNP",
        "arguments": {},
        "project_root": "C:\\Work",
        "drawing_id": None,
        "fingerprint": None,
        "progress": None,
        "snapshot_id": None,
        "report_id": None,
        "error": None,
        "warnings": [],
        "documents": [],
        "next_op_seq": 1,
    }
    parsed = JobRecord.from_json(v0_payload)
    assert parsed.part_result is None
    # to_json without part_result does not include part_result or is None
    assert parsed.to_json().get("part_result") is None

    # Payload with part_result
    part_result_data: Obj = {
        "path": "C:\\Work\\part.SLDPRT",
        "fingerprint": FP_A,
        "checks": [{"name": "volume", "passed": True}],
        "measured": {"volume_m3": 0.0001},
        "feature_ids": {"sketch1": "f1", "extrude1": "f2"},
        "template": "C:\\Work\\template.prtdot",
    }
    with_part_result: Obj = dict(v0_payload)
    with_part_result["part_result"] = part_result_data
    parsed_with = JobRecord.from_json(with_part_result)
    assert parsed_with.part_result == part_result_data
    assert parsed_with.to_json()["part_result"] == part_result_data


def test_plan_reuse() -> None:
    store, _, _, _ = _env()
    plan: JsonValue = {"compiler_version": "0.1.0", "operations": []}
    plan_hash = "plan_hash_12345"

    first = store.put_plan(plan_hash, plan)
    assert first is True

    # Writing same plan twice returns False second time
    second = store.put_plan(plan_hash, plan)
    assert second is False


def test_revision_rules() -> None:
    store, _, _, _ = _env()
    doc_v1: JsonValue = {"units": "mm", "features": [{"name": "base"}]}
    doc_v2: JsonValue = {"units": "mm", "features": [{"name": "base"}, {"name": "hole"}]}

    # 1. New ID gives 1
    ref1 = store.put_part_revision("part:bracket", doc_v1, expected_revision=None)
    assert ref1 == "part:bracket@1"

    # Also works without "part:" prefix
    ref_other = store.put_part_revision("plate", doc_v1, expected_revision=None)
    assert ref_other == "part:plate@1"

    # Check read back
    loaded_rev1 = store.get_part_revision("part:bracket@1")
    assert isinstance(loaded_rev1, dict)
    assert loaded_rev1["revision"] == 1
    assert loaded_rev1["features"] == [{"name": "base"}]

    # Reading without rev gives latest (rev 1)
    loaded_latest = store.get_part_revision("part:bracket")
    assert isinstance(loaded_latest, dict)
    assert loaded_latest["revision"] == 1

    # 2. Same content reuses it (no new revision created)
    # Even if expected_revision is None or 1, same content returns existing revision
    ref1_reuse = store.put_part_revision("part:bracket", doc_v1, expected_revision=None)
    assert ref1_reuse == "part:bracket@1"

    ref1_reuse_explicit = store.put_part_revision("part:bracket", doc_v1, expected_revision=1)
    assert ref1_reuse_explicit == "part:bracket@1"

    # 3. Changed content needs expected_revision, else REV_CONFLICT
    conflict_none = store.put_part_revision("part:bracket", doc_v2, expected_revision=None)
    assert isinstance(conflict_none, StoreError)
    assert conflict_none.code == "REV_CONFLICT"
    assert conflict_none.details == {"latest": 1, "expected": None}

    conflict_wrong = store.put_part_revision("part:bracket", doc_v2, expected_revision=2)
    assert isinstance(conflict_wrong, StoreError)
    assert conflict_wrong.code == "REV_CONFLICT"
    assert conflict_wrong.details == {"latest": 1, "expected": 2}

    # 4. Matching expected_revision increments
    ref2 = store.put_part_revision("part:bracket", doc_v2, expected_revision=1)
    assert ref2 == "part:bracket@2"

    loaded_rev2 = store.get_part_revision("part:bracket@2")
    assert isinstance(loaded_rev2, dict)
    assert loaded_rev2["revision"] == 2  # noqa: PLR2004
    assert loaded_rev2["features"] == [{"name": "base"}, {"name": "hole"}]

    loaded_latest2 = store.get_part_revision("part:bracket")
    assert isinstance(loaded_latest2, dict)
    assert loaded_latest2["revision"] == 2  # noqa: PLR2004


def test_part_record_round_trip() -> None:
    store, _, _, _ = _env()
    record = PartRecord(
        part_key="fp-1234567890abcdef",
        path="C:\\Work\\bracket.SLDPRT",
        fingerprint=FP_A,
        produced=True,
        graph="part:bracket@2",
        job_id="job_01H1234567890ABCDEFGHJKMNP",
        updated_at=TS,
    )
    store.put_part_record(record)

    loaded = store.get_part_record("fp-1234567890abcdef")
    assert isinstance(loaded, PartRecord)
    assert loaded == record
