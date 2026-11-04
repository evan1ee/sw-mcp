"""get_execution_status and cancel_execution (spec 12.4.5, ADR-043), ids and summary lines."""

import threading
from dataclasses import replace

import pytest
from cad_application.ports import BackendUnavailable
from cad_application.store.job_records import JobDocument
from cad_application.store.records import JobWarning
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import make_hello
from cad_application.testing.job_rig import DRAWING
from cad_application.testing.tool_rig import ToolRig, make_tool_rig
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]

GUARD_S = 5.0
UNKNOWN_JOB = "job_00000000000000000000000077"
JOB_ONE = "job_00000000000000000000000001"
REQ_ONE = "req_00000000000000000000000001"
MAX_WAIT_MS = 20_000
MAX_WAIT_S = 20.0
STEP_READ_BACK = 2
STEPS = 4
POLL_HINT_MS = 1000
ELAPSED_S = 2.5


def _submit(rig: ToolRig) -> str:
    rig.write_drawing(DRAWING)
    result = rig.call("check_drawing", {"path": DRAWING})
    return str(ToolRig.data_of(result)["execution_id"])


def _status(rig: ToolRig, job_id: str, **extra: JsonValue) -> Doc:
    return ToolRig.data_of(rig.call("get_execution_status", {"execution_id": job_id, **extra}))


class _Running:
    """A job blocked inside the backend, on a worker thread, in state EXECUTING."""

    def __init__(self, rig: ToolRig, block: threading.Event) -> None:
        self.rig, self.block = rig, block
        self.worker = threading.Thread(target=rig.rig.engine.run_next)

    def start(self) -> None:
        self.worker.start()
        assert self.rig.rig.backend.snapshot_started.wait(GUARD_S)

    def finish(self) -> None:
        self.block.set()
        self.worker.join(GUARD_S)
        assert not self.worker.is_alive()


def _running(clock: FakeClock | None = None) -> tuple[ToolRig, str, _Running]:
    block = threading.Event()
    rig = make_tool_rig(block=block, clock=clock)
    job_id = _submit(rig)
    running = _Running(rig, block)
    running.start()
    return rig, job_id, running


# --- status per state ---------------------------------------------------------------------


def test_status_fields_per_state_planned() -> None:
    rig = make_tool_rig()
    job_id = _submit(rig)
    assert _status(rig, job_id) == {
        "execution_id": job_id,
        "job_type": "check_drawing",
        "state": "PLANNED",
        "queued_position": 0,
        "started_at": None,
        "retry_after_ms": POLL_HINT_MS,
        "warnings": [],
        "documents_unknown": [],
    }


def test_status_fields_per_state_executing() -> None:
    clock = FakeClock()
    rig, job_id, running = _running(clock)
    clock.advance(ELAPSED_S)
    data = _status(rig, job_id)
    running.finish()
    assert data["state"] == "EXECUTING"
    assert data["progress"] == {
        "step": STEP_READ_BACK,
        "of": STEPS,
        "message": "reading the drawing back",
    }
    assert data["elapsed_ms"] == int(ELAPSED_S * 1000)
    assert isinstance(data["started_at"], str)
    assert data["retry_after_ms"] == POLL_HINT_MS
    for absent in ("queued_position", "report_id", "error"):
        assert absent not in data


def test_status_fields_per_state_committed(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = _submit(rig)
    assert rig.rig.engine.run_next()
    data = _status(rig, job_id)
    assert data["state"] == "COMMITTED"
    assert data["report_id"] == rig.rig.job(job_id).report_id
    assert isinstance(data["started_at"], str)
    assert isinstance(data["elapsed_ms"], int)
    for absent in ("queued_position", "progress", "retry_after_ms", "error"):
        assert absent not in data


def test_status_fields_per_state_failed() -> None:
    rig = make_tool_rig(unavailable=BackendUnavailable("BACKEND_LOST", "no session"))
    job_id = _submit(rig)
    assert rig.rig.engine.run_next()
    data = _status(rig, job_id)
    assert data["state"] == "FAILED"
    error = data["error"]
    assert isinstance(error, dict)
    assert error["code"] == "BACKEND_LOST"
    assert set(error) >= {"code", "message", "retryable"}
    for absent in ("report_id", "retry_after_ms", "progress", "queued_position"):
        assert absent not in data


def test_status_fields_per_state_aborted() -> None:
    rig = make_tool_rig()
    job_id = _submit(rig)
    rig.call("cancel_execution", {"execution_id": job_id})
    data = _status(rig, job_id)
    assert data["state"] == "ABORTED"
    assert data["started_at"] is None
    assert "elapsed_ms" not in data
    error = data["error"]
    assert isinstance(error, dict)
    assert error["code"] == "EXEC_CANCELLED"


def test_status_shows_job_warnings(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot, hello=make_hello(warnings=["SP2 is old"]))
    job_id = _submit(rig)
    assert rig.rig.engine.run_next()
    warnings = _status(rig, job_id)["warnings"]
    assert isinstance(warnings, list)
    first = warnings[0]
    assert isinstance(first, dict)
    assert first["code"] == "solidworks_version_warning"


def test_status_after_restart_lists_documents_unknown() -> None:
    rig = make_tool_rig(unavailable=BackendUnavailable("BACKEND_LOST", "no session"))
    job_id = _submit(rig)
    assert rig.rig.engine.run_next()
    stored = rig.rig.job(job_id)
    unknown = JobDocument(DRAWING, True, "unknown")
    warning = JobWarning("w", "kept")
    rig.rig.store().put_job(replace(stored, documents=(unknown,), warnings=(warning,)))
    rig.rig.stores.close_all()
    restarted = make_tool_rig(fs=rig.rig.fs)
    restarted.rig.engine.recover_all()
    data = _status(restarted, job_id)
    assert data["state"] == "FAILED"
    assert data["documents_unknown"] == [DRAWING]
    assert data["warnings"] == [{"code": "w", "message": "kept"}]


# --- long-poll ----------------------------------------------------------------------------


def test_status_wait_expires_without_real_time() -> None:
    clock = FakeClock()
    rig = make_tool_rig(clock=clock)
    job_id = _submit(rig)
    data = _status(rig, job_id, wait_ms=MAX_WAIT_MS)
    assert data["state"] == "PLANNED"
    assert data["retry_after_ms"] == POLL_HINT_MS
    assert clock.monotonic_s() == pytest.approx(MAX_WAIT_S)


def test_status_wait_on_final_job_returns_at_once(good_snapshot: Doc) -> None:
    clock = FakeClock()
    rig = make_tool_rig(snapshot=good_snapshot, clock=clock)
    job_id = _submit(rig)
    assert rig.rig.engine.run_next()
    before = clock.monotonic_s()
    assert _status(rig, job_id, wait_ms=MAX_WAIT_MS)["state"] == "COMMITTED"
    assert clock.monotonic_s() == before


def test_status_retry_after_is_zero_on_a_state_change() -> None:
    block = threading.Event()

    class _StartsTheJob(FakeClock):
        """While the poller waits (lock free), the worker starts and blocks in the backend."""

        running: _Running | None = None

        def wait(self, cond: threading.Condition, timeout_s: float) -> None:
            assert self.running is not None
            cond.release()
            try:
                self.running.start()
            finally:
                cond.acquire()

    clock = _StartsTheJob()
    rig = make_tool_rig(block=block, clock=clock)
    job_id = _submit(rig)
    clock.running = _Running(rig, block)
    data = _status(rig, job_id, wait_ms=MAX_WAIT_MS)
    clock.running.finish()
    assert data["state"] == "EXECUTING"
    assert data["retry_after_ms"] == 0


def test_status_retry_after() -> None:
    rig = make_tool_rig()
    job_id = _submit(rig)
    assert _status(rig, job_id)["retry_after_ms"] == POLL_HINT_MS
    assert _status(rig, job_id, wait_ms=0)["retry_after_ms"] == POLL_HINT_MS


# --- cancel -------------------------------------------------------------------------------


def test_cancel_planned_job_is_aborted_before_returning() -> None:
    rig = make_tool_rig()
    job_id = _submit(rig)
    result = rig.call("cancel_execution", {"execution_id": job_id})
    assert ToolRig.data_of(result) == {
        "execution_id": job_id,
        "state": "ABORTED",
        "final": True,
        "changes": [],
    }
    assert result.summary == f"{job_id} ABORTED"
    assert not rig.rig.engine.run_next()


def test_cancel_output_changes_empty(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = _submit(rig)
    for keep in (True, False):
        data = ToolRig.data_of(
            rig.call("cancel_execution", {"execution_id": job_id, "keep_partial": keep})
        )
        assert data["changes"] == []


def test_cancel_finished_job_is_returned_not_an_error(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = _submit(rig)
    assert rig.rig.engine.run_next()
    result = rig.call("cancel_execution", {"execution_id": job_id})
    assert ToolRig.data_of(result) == {
        "execution_id": job_id,
        "state": "COMMITTED",
        "final": True,
        "changes": [],
    }
    assert result.summary == f"{job_id} COMMITTED"


def test_cancel_running_job_returns_at_once_not_final() -> None:
    rig, job_id, running = _running()
    result = rig.call("cancel_execution", {"execution_id": job_id})
    running.finish()
    assert ToolRig.data_of(result) == {
        "execution_id": job_id,
        "state": "EXECUTING",
        "final": False,
        "changes": [],
    }
    assert result.summary == f"cancel requested: {job_id} EXECUTING"
    assert _status(rig, job_id)["state"] == "ABORTED"


# --- ids, summaries, errors ---------------------------------------------------------------


def test_ids_per_tool(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    rig.write_drawing(DRAWING)
    queued = rig.call("check_drawing", {"path": DRAWING})
    assert ToolRig.ids_of(queued) == {"request_id": REQ_ONE, "execution_id": JOB_ONE}
    argument: Doc = {"execution_id": JOB_ONE}
    for tool in ("get_execution_status", "cancel_execution"):
        ids = ToolRig.ids_of(rig.call(tool, argument))
        assert set(ids) == {"request_id", "execution_id"}
        assert ids["execution_id"] == JOB_ONE
        assert ids["request_id"].startswith("req_")
    missing = ToolRig.ids_of(rig.call("get_execution_status", {"execution_id": UNKNOWN_JOB}))
    assert set(missing) == {"request_id", "execution_id"}
    invalid = ToolRig.ids_of(rig.call("get_execution_status", {"execution_id": 5}))
    assert set(invalid) == {"request_id"}
    denied = ToolRig.ids_of(rig.call("check_drawing", {"path": "D:\\x\\a.slddrw"}))
    assert set(denied) == {"request_id"}


def test_request_ids_are_distinct_per_call() -> None:
    rig = make_tool_rig()
    first = ToolRig.ids_of(rig.call("get_execution_status", {"execution_id": UNKNOWN_JOB}))
    second = ToolRig.ids_of(rig.call("get_execution_status", {"execution_id": UNKNOWN_JOB}))
    assert first["request_id"] != second["request_id"]


def test_summary_lines() -> None:
    clock = FakeClock()
    rig, job_id, running = _running(clock)
    executing = rig.call("get_execution_status", {"execution_id": job_id})
    running.finish()
    assert executing.summary == f"{job_id} check_drawing EXECUTING (2/4 reading the drawing back)"
    planned = make_tool_rig()
    planned_id = _submit(planned)
    assert planned.call("get_execution_status", {"execution_id": planned_id}).summary == (
        f"{planned_id} check_drawing PLANNED (position 0)"
    )
    failed = make_tool_rig(unavailable=BackendUnavailable("BACKEND_LOST", "no session"))
    failed_id = _submit(failed)
    assert failed.rig.engine.run_next()
    assert failed.call("get_execution_status", {"execution_id": failed_id}).summary == (
        f"{failed_id} check_drawing FAILED (BACKEND_LOST)"
    )
    missing = planned.call("get_execution_status", {"execution_id": UNKNOWN_JOB})
    assert missing.summary.startswith("EXEC_NOT_FOUND: ")
    assert planned.call("check_drawing", {"path": "D:\\x\\a.slddrw"}).summary.startswith(
        "AUTH_PATH_DENIED"
    )
    assert all(len(s) <= 200 for s in (executing.summary, missing.summary))  # noqa: PLR2004


def test_committed_summary_line(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = _submit(rig)
    assert rig.rig.engine.run_next()
    report_id = rig.rig.job(job_id).report_id
    summary = rig.call("get_execution_status", {"execution_id": job_id}).summary
    assert summary == f"{job_id} check_drawing COMMITTED (report {report_id})"
