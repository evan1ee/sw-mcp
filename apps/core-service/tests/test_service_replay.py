"""CoreService end to end over replayed transcripts: real files, a real worker thread.

Every wait goes through ``get_execution_status`` with ``wait_ms``; nothing sleeps.
"""

import threading
from collections.abc import Callable

from cad_application.ports import BackendUnavailable
from cad_application.store.file_store import FileStore
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import FakeBackend, FakeBackendProvider, make_hello
from cad_ir.core.json_types import JsonValue
from core_service.os_fs import OsFileSystem
from core_service.testing import CrashableFileSystem, ServiceRig

type RigFactory = Callable[..., ServiceRig]

GUARD_S = 5.0


def _actions(rig: ServiceRig, job_id: str) -> list[str]:
    return [str(r["action"]) for r in rig.journal(job_id) if r["type"] == "document"]


def _report(rig: ServiceRig, report_id: JsonValue) -> dict[str, JsonValue]:
    return rig.data(rig.call("get_drawing_report", {"report_id": report_id}))


def test_owned_drawing_commits_and_closes(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_owned")
    job = rig.submit()
    final = rig.wait_final(job)
    assert final["state"] == "COMMITTED"
    assert final["warnings"] == []
    assert final["documents_unknown"] == []
    assert str(final["report_id"]).startswith("rep_")
    assert _actions(rig, job) == ["open", "close"]
    assert rig.snapshot_files()


def test_borrowed_drawing_commits_without_close(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_borrowed")
    job = rig.submit()
    final = rig.wait_final(job)
    assert final["state"] == "COMMITTED"
    assert final["warnings"] == []  # a stray close would have failed against the transcript
    assert _actions(rig, job) == ["open"]


def test_bad_sheet_fails(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_bad_sheet")
    job = rig.submit(["Nope"])
    final = rig.wait_final(job)
    assert final["state"] == "FAILED"
    error = final["error"]
    assert isinstance(error, dict)
    assert error["code"] == "IR_REFERENCE_UNRESOLVED"
    assert "report_id" not in final
    assert _actions(rig, job) == ["open", "close"]  # the drawing it opened is closed again
    assert rig.snapshot_files() == []


def test_ui_blocked_fails(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_ui_blocked")
    job = rig.submit()
    final = rig.wait_final(job)
    assert final["state"] == "FAILED"
    error = final["error"]
    assert isinstance(error, dict)
    assert error["code"] == "BACKEND_UI_BLOCKED"
    assert final["documents_unknown"] == [rig.drawing]
    assert rig.snapshot_files() == []  # the result of the call was discarded


def test_timeout_fails(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_timeout")
    final = rig.wait_final(rig.submit())
    error = final["error"]
    assert final["state"] == "FAILED"
    assert isinstance(error, dict)
    assert error["code"] == "EXEC_TIMEOUT"
    assert final["documents_unknown"] == [rig.drawing]


def test_backend_lost_fails(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_lost")
    final = rig.wait_final(rig.submit())
    error = final["error"]
    assert final["state"] == "FAILED"
    assert isinstance(error, dict)
    assert error["code"] == "BACKEND_LOST"


def test_sp_warning_reaches_status_and_report(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_sp_warning")
    final = rig.wait_final(rig.submit())
    assert final["state"] == "COMMITTED"
    warnings = final["warnings"]
    assert isinstance(warnings, list)
    assert [w["code"] for w in warnings if isinstance(w, dict)] == ["solidworks_version_warning"]
    report = _report(rig, final["report_id"])
    reported = report["job_warnings"]
    assert isinstance(reported, list)
    assert [w["code"] for w in reported if isinstance(w, dict)] == ["solidworks_version_warning"]


def test_report_readable_through_the_tool(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_owned")
    final = rig.wait_final(rig.submit())
    report = _report(rig, final["report_id"])
    assert report["verdict"] in {"done", "fail", "not_evaluated"}


def test_unavailable_backend_fails_the_job_not_the_call(start_rig: RigFactory) -> None:
    unavailable = BackendUnavailable("BACKEND_SESSION_AMBIGUOUS", "Two sessions.")
    rig = start_rig(provider=FakeBackendProvider(None, unavailable))
    final = rig.wait_final(rig.submit())
    error = final["error"]
    assert isinstance(error, dict)
    assert error["code"] == "BACKEND_SESSION_AMBIGUOUS"


def test_restart_recovers_interrupted_job(start_rig: RigFactory) -> None:
    release = threading.Event()
    backend = FakeBackend(make_hello(), block=release)
    crashing = CrashableFileSystem()
    first = start_rig(provider=FakeBackendProvider(backend), fs=crashing)
    job = first.submit()
    assert backend.snapshot_started.wait(GUARD_S)  # the worker is inside the snapshot call
    first.wait_for_state(job, "EXECUTING")
    crashing.crash()  # the process dies here: writes fail and the locks are released
    release.set()
    first.stop()
    second = start_rig(provider=FakeBackendProvider(FakeBackend(make_hello())))
    recovered = second.status(job)
    assert recovered["state"] == "FAILED"
    error = recovered["error"]
    assert isinstance(error, dict)
    assert error["code"] == "EXEC_INTERRUPTED"
    assert recovered["documents_unknown"] == [second.drawing]


def test_report_readable_after_restart(start_rig: RigFactory) -> None:
    first = start_rig("check_drawing_owned")
    job = first.submit()
    final = first.wait_final(job)
    before = _report(first, final["report_id"])
    first.stop()
    second = start_rig(provider=FakeBackendProvider(FakeBackend(make_hello())))
    again = second.status(job)
    assert again["state"] == "COMMITTED"
    assert again["report_id"] == final["report_id"]
    assert _report(second, final["report_id"]) == before


def test_stop_is_idempotent_and_releases_the_store(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_owned")
    rig.wait_final(rig.submit())
    rig.stop()
    rig.stop()
    reopened = FileStore.open(
        OsFileSystem(), str(rig.project / ".cad"), str(rig.project), FakeClock()
    )
    assert isinstance(reopened, FileStore)
    reopened.close()
