"""The check_drawing job over fakes (spec 8.4, 11.5.4, ADR-046)."""

import json
from collections.abc import Callable
from typing import cast

import pytest
from cad_application.config.settings import Settings
from cad_application.ports import BackendCallError, BackendUnavailable
from cad_application.store.job_records import JobDocument, JobRecord
from cad_application.store.journal_records import BatchSentRecord, JournalRecord, StateRecord
from cad_application.testing.fakes import FakeBackend, RecordedCall, make_hello
from cad_application.testing.job_rig import DRAWING, Rig, make_rig
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_drawing.checks import build_report
from cad_drawing.checks.report import DrawingReport
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import OperationGroup

type Doc = dict[str, JsonValue]

SNAPSHOTS_DIR = "C:\\Work\\.cad\\snapshots"
STEPS = [1, 2, 3, 4]


def _run(rig: Rig) -> JobRecord:
    job = rig.submit()
    assert rig.engine.run_next()
    return rig.job(job.job_id)


def _code(record: JobRecord) -> object:
    return None if record.error is None else record.error["code"]


def _ops(rig: Rig) -> list[str]:
    """The operation names sent, in order."""
    names: list[str] = []
    for call in rig.backend.calls:
        if call.name == "apply_ops":
            groups = cast("tuple[OperationGroup, ...]", call.args[0])
            names.extend(op.op for g in groups for op in g.operations)
    return names


def _expected(doc: Doc) -> JsonValue:
    report = build_report(doc, thresholds=Settings().check_thresholds(), title_block_mappings={})
    assert isinstance(report, DrawingReport)
    return report.to_json()


def _transitions(rig: Rig, job_id: str) -> list[tuple[str | None, str]]:
    return [(r.from_state, r.to) for r in rig.journal(job_id) if isinstance(r, StateRecord)]


def _stored(rig: Rig) -> list[str]:
    """Names under the snapshots folder: empty when nothing was stored."""
    if rig.fs.stat(SNAPSHOTS_DIR) is None:
        return []
    return list(rig.fs.list_dir(SNAPSHOTS_DIR))


def test_fail_verdict_commits(failing_snapshot: Doc) -> None:
    expected = _expected(failing_snapshot)
    assert isinstance(expected, dict)
    assert expected["verdict"] == "fail"
    rig = make_rig(snapshot=failing_snapshot)
    record = _run(rig)
    assert record.state == "COMMITTED"
    assert record.error is None
    assert record.report_id is not None
    report, _ = rig.report(record.report_id)
    assert report["verdict"] == "fail"


@pytest.mark.parametrize("fixture", ["good_snapshot", "failing_snapshot"])
def test_report_calibration_unverified(fixture: str, request: pytest.FixtureRequest) -> None:
    rig = make_rig(snapshot=request.getfixturevalue(fixture))
    record = _run(rig)
    assert record.report_id is not None
    report, _ = rig.report(record.report_id)
    calibration = report["calibration"]
    assert isinstance(calibration, dict)
    assert calibration["status"] == "unverified"


def test_stored_report_is_exactly_build_report(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    record = _run(rig)
    assert record.report_id is not None
    report, meta = rig.report(record.report_id)
    assert report == _expected(good_snapshot)
    assert meta.execution_id == record.job_id
    assert meta.snapshot_id == record.snapshot_id


def test_batch_sent_flushed_before_apply(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()
    seen: list[JournalRecord] = []

    def before(name: str) -> None:
        if name == "apply_ops":
            seen.append(rig.journal(job.job_id)[-1])

    rig.backend.before = before
    assert rig.engine.run_next()
    assert [isinstance(r, BatchSentRecord) for r in seen] == [True, True]
    ids = [r.operation_ids for r in seen if isinstance(r, BatchSentRecord)]
    assert ids == [(f"{job.job_id}:1",), (f"{job.job_id}:2",)]


def test_states_run_in_order(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    record = _run(rig)
    assert _transitions(rig, record.job_id) == [
        (None, "PLANNED"),
        ("PLANNED", "VALIDATED"),
        ("VALIDATED", "EXECUTING"),
        ("EXECUTING", "VERIFYING"),
        ("VERIFYING", "COMMITTED"),
    ]
    assert record.started_at is not None
    assert record.ended_at is not None


def test_borrowed_drawing_not_closed(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot, open_owned=False)
    record = _run(rig)
    assert record.state == "COMMITTED"
    assert _ops(rig) == ["document.open"]
    assert record.documents == (JobDocument(DRAWING, False, "known"),)


def test_owned_drawing_is_closed_on_success(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    record = _run(rig)
    assert _ops(rig) == ["document.open", "document.close"]
    assert record.documents == ()


def test_cancelled_job_closes_owned_drawing(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()

    def cancel_during_read(name: str) -> None:
        if name == "snapshot_drawing":
            rig.engine.cancel(job.job_id)

    rig.backend.after = cancel_during_read
    assert rig.engine.run_next()
    record = rig.job(job.job_id)
    assert (record.state, _code(record)) == ("ABORTED", "EXEC_CANCELLED")
    assert _ops(rig) == ["document.open", "document.close"]
    assert rig.backend.cancel_called
    assert rig.drawings() == ()
    assert _stored(rig) == []


def test_cancel_between_open_and_snapshot(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()
    fired: list[bool] = []

    def cancel_after_open(name: str) -> None:
        if name == "apply_ops" and not fired:
            fired.append(True)
            rig.engine.cancel(job.job_id)

    rig.backend.after = cancel_after_open
    assert rig.engine.run_next()
    record = rig.job(job.job_id)
    assert (record.state, _code(record)) == ("ABORTED", "EXEC_CANCELLED")
    assert "snapshot_drawing" not in [c.name for c in rig.backend.calls]
    assert _ops(rig) == ["document.open", "document.close"]


class _CancelOnReportFs(MemoryFileSystem):
    """Calls ``on_report`` when the first file of the reports folder is written."""

    def __init__(self) -> None:
        super().__init__()
        self.on_report: Callable[[], None] = lambda: None

    def write_new(self, path: str, data: bytes) -> None:
        super().write_new(path, data)
        if "reports" in path.lower():
            hook, self.on_report = self.on_report, lambda: None
            hook()


def test_cancel_after_report_write_commits(good_snapshot: Doc) -> None:
    fs = _CancelOnReportFs()
    rig = make_rig(snapshot=good_snapshot, fs=fs)
    job = rig.submit()
    fs.on_report = lambda: rig.engine.cancel(job.job_id) and None
    assert rig.engine.run_next()
    record = rig.job(job.job_id)
    assert record.state == "COMMITTED"
    assert record.report_id is not None
    assert rig.backend.cancel_called
    assert _ops(rig) == ["document.open", "document.close"]


@pytest.mark.parametrize("code", ["BACKEND_LOST", "BACKEND_SESSION_AMBIGUOUS"])
def test_backend_unavailable_fails_from_planned(code: str) -> None:
    rig = make_rig(unavailable=BackendUnavailable(code, "no session"))
    record = _run(rig)
    assert (record.state, _code(record)) == ("FAILED", code)
    assert _transitions(rig, record.job_id)[-1] == ("PLANNED", "FAILED")
    assert record.started_at is None


@pytest.mark.parametrize(
    "hello",
    [
        make_hello(capabilities=("ops.apply",)),
        make_hello(capabilities=("drawing.snapshot",)),
        make_hello(operations=("document.open",)),
    ],
)
def test_missing_capability_fails(hello: object) -> None:
    rig = make_rig(hello=hello)  # type: ignore[arg-type]
    record = _run(rig)
    assert (record.state, _code(record)) == ("FAILED", "BACKEND_CAPABILITY_MISSING")
    assert _transitions(rig, record.job_id)[-1] == ("PLANNED", "FAILED")
    assert rig.backend.calls == []


def test_timeout_fails_with_exec_timeout(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)

    def time_out(name: str) -> None:
        if name == "snapshot_drawing":
            raise BackendCallError("EXEC_TIMEOUT", "no answer in time")

    rig.backend.before = time_out
    record = _run(rig)
    assert (record.state, _code(record)) == ("FAILED", "EXEC_TIMEOUT")
    assert _ops(rig) == ["document.open"]  # no close is queued behind a command that may run
    assert record.documents == (JobDocument(DRAWING, True, "unknown"),)


def _notify_after_read(rig: Rig, method: str, params: JsonValue) -> None:
    def after(name: str) -> None:
        if name == "snapshot_drawing":
            rig.provider.notify(method, params)

    rig.backend.after = after


def test_ui_blocked_fails_job_and_stores_nothing(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    _notify_after_read(rig, "session.ui_blocked", {"waited_ms": 30000})
    record = _run(rig)
    assert (record.state, _code(record)) == ("FAILED", "BACKEND_UI_BLOCKED")
    assert record.snapshot_id is None
    assert record.report_id is None
    assert _stored(rig) == []
    assert rig.drawings() == ()
    assert _ops(rig) == ["document.open"]


def test_document_event_interrupts(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    _notify_after_read(rig, "document.event", {"document": DRAWING.upper(), "event": "save"})
    record = _run(rig)
    assert (record.state, _code(record)) == ("FAILED", "EXEC_INTERRUPTED_BY_USER")
    assert _stored(rig) == []
    assert _ops(rig) == ["document.open"]  # the user is working in it: never closed


@pytest.mark.parametrize(
    "params",
    [
        {"document": "C:\\Work\\other.slddrw", "event": "save"},
        {
            "document": DRAWING,
            "event": "regen",
            "_meta": {"job_id": "job_00000000000000000000000001"},
        },
    ],
    ids=["other_document", "caused_by_this_job"],
)
def test_events_that_are_not_foreign_are_ignored(good_snapshot: Doc, params: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    _notify_after_read(rig, "document.event", params)
    assert _run(rig).state == "COMMITTED"


def test_invalid_snapshot_fails_with_issue_code() -> None:
    rig = make_rig(snapshot={"schema_version": "0.1"})
    record = _run(rig)
    assert (record.state, _code(record)) == ("FAILED", "IR_SCHEMA_INVALID")
    assert record.report_id is None
    assert _transitions(rig, record.job_id)[-1] == ("EXECUTING", "FAILED")  # 13.2.3: before storing
    assert _stored(rig) == []
    assert _ops(rig) == ["document.open", "document.close"]


def test_service_pack_warning_on_job(good_snapshot: Doc) -> None:
    text = "SOLIDWORKS 2025 SP5 is newer than the tested service pack."
    rig = make_rig(snapshot=good_snapshot, hello=make_hello(warnings=(text,)))
    record = _run(rig)
    assert [(w.code, w.message) for w in record.warnings] == [("solidworks_version_warning", text)]
    assert record.report_id is not None
    report, meta = rig.report(record.report_id)
    assert [w.message for w in meta.job_warnings] == [text]
    assert text not in json.dumps(report)  # the report file stays a pure function (11.5.4)


def test_d8_not_evaluated_without_mapping(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    record = _run(rig)
    assert record.report_id is not None
    report, _ = rig.report(record.report_id)
    checks = cast("dict[str, dict[str, JsonValue]]", report["checks"])
    assert checks["D8"]["status"] == "not_evaluated"
    assert checks["D8"]["reasons"] == ["title_block_mapping_missing"]


def test_meta_carries_request_and_job_ids(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    record = _run(rig)
    metas: list[tuple[str, str | None, str | None, str | None]] = []
    for call in rig.backend.calls:
        assert isinstance(call, RecordedCall)
        assert call.meta is not None
        metas.append((call.name, call.meta.request_id, call.meta.job_id, call.meta.operation_id))
    job_id, request_id = record.job_id, record.request_id
    assert metas == [
        ("apply_ops", request_id, job_id, f"{job_id}:1"),
        ("snapshot_drawing", request_id, job_id, None),
        ("apply_ops", request_id, job_id, f"{job_id}:2"),
    ]


def test_progress_steps_1_to_4(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    record = _run(rig)
    steps = [e.fields["count"] for e in rig.log.events if e.event == "job.progress"]
    assert steps == STEPS
    assert record.progress is not None
    assert (record.progress.step, record.progress.of) == (4, 4)


def test_drawing_record_is_updated_and_reused(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    first = _run(rig)
    second = _run(rig)
    drawings = rig.drawings()
    assert len(drawings) == 1
    assert first.drawing_id == second.drawing_id == drawings[0].drawing_id
    assert drawings[0].latest_report_id == second.report_id
    assert drawings[0].latest_snapshot_id == second.snapshot_id


def test_sheets_are_passed_to_the_snapshot(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit(("Sheet1",))
    assert rig.engine.run_next()
    read = next(c for c in rig.backend.calls if c.name == "snapshot_drawing")
    assert read.args == (DRAWING, ("Sheet1",))
    assert rig.job(job.job_id).arguments == {"path": DRAWING, "sheets": ["Sheet1"]}


def test_refused_open_fails_with_the_backend_code() -> None:
    class _Refusing(FakeBackend):
        def apply_ops(self, groups, *, meta=None):  # type: ignore[no-untyped-def]
            raise BackendCallError("AUTH_PATH_DENIED", "denied")

    rig = make_rig(backend=_Refusing(make_hello()))
    record = _run(rig)
    assert (record.state, _code(record)) == ("FAILED", "AUTH_PATH_DENIED")


class _FullDisk(MemoryFileSystem):
    """A disk that is full once the snapshot is written."""

    def write_new(self, path: str, data: bytes) -> None:
        if "snapshots" in path.lower():
            raise OSError(28, "No space left on device")
        super().write_new(path, data)


def test_store_write_failure_closes_owned_drawing(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot, fs=_FullDisk())
    record = _run(rig)
    assert record.state == "FAILED"
    assert _code(record) == "STORE_UNAVAILABLE"
    assert _ops(rig) == ["document.open", "document.close"]
    assert record.documents == ()
