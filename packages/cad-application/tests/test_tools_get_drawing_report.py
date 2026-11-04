"""The get_drawing_report handler (spec 12.4.5, 12.3 token budget): lookups and summaries."""

import json
from collections.abc import Callable
from typing import cast

import pytest
from cad_application.ports import BackendUnavailable
from cad_application.store.records import DrawingRecord, ReportMeta
from cad_application.testing.builders import STORE_DIR
from cad_application.testing.fakes import make_hello
from cad_application.testing.job_rig import DRAWING, FINGERPRINT
from cad_application.testing.report_rig import (
    FAILURES,
    WARNINGS,
    base_report,
    commit_job,
    seed_report,
    stored_report,
    unevaluated_report,
    worst_report,
)
from cad_application.testing.tool_rig import ToolRig, make_tool_rig
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]

SUMMARY_KEYS = {
    "report_id",
    "execution_id",
    "drawing",
    "verdict",
    "calibration",
    "checks",
    "conflict_count",
    "top_failures",
    "warning_count",
    "job_warnings",
    "links",
}
TOKEN_BUDGET = 600
BYTES_PER_TOKEN = 4
UNKNOWN_REPORT = "rep_00000000000000000000000077"
UNKNOWN_JOB = "job_00000000000000000000000077"


# --- summary ------------------------------------------------------------------------------


def test_report_summary_fields(failing_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=failing_snapshot)
    job_id = commit_job(rig)
    report = stored_report(rig, job_id)
    record = rig.rig.job(job_id)
    result = rig.call("get_drawing_report", {"execution_id": job_id})
    data = ToolRig.data_of(result)
    assert set(data) == SUMMARY_KEYS
    assert data["report_id"] == record.report_id
    assert data["execution_id"] == job_id
    assert data["drawing"] == {"path": DRAWING, "drawing_id": record.drawing_id}
    assert data["verdict"] == "fail" == report["verdict"]
    assert data["calibration"] == report["calibration"]
    assert data["conflict_count"] == report["conflict_count"]
    assert data["warning_count"] == len(cast("list[JsonValue]", report["warnings"]))
    assert data["job_warnings"] == []
    assert data["links"] == {
        "report": f"cad://reports/{record.report_id}",
        "snapshot": f"cad://snapshots/{record.snapshot_id}",
    }
    checks = cast("dict[str, Doc]", data["checks"])
    expected = cast("dict[str, Doc]", report["checks"])
    assert list(checks) == [f"D{n}" for n in range(1, 11)]
    for name, entry in checks.items():
        assert entry == {k: expected[name][k] for k in ("status", "failure_count", "reasons")}
    top = cast("list[Doc]", data["top_failures"])
    failures = cast("list[Doc]", report["failures"])
    assert len(top) == min(5, len(failures))
    assert top
    assert top[0]["check"] == failures[0]["check"]
    assert top[0]["code"] == failures[0].get("code")


def test_report_by_report_id_matches_by_execution_id(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = commit_job(rig)
    report_id = rig.rig.job(job_id).report_id
    by_job = ToolRig.data_of(rig.call("get_drawing_report", {"execution_id": job_id}))
    by_report = ToolRig.data_of(rig.call("get_drawing_report", {"report_id": report_id}))
    assert by_job == by_report


def test_top_failures_are_the_first_five_with_three_ids() -> None:
    rig = make_tool_rig()
    report_id, job_id = seed_report(rig, worst_report())
    data = ToolRig.data_of(rig.call("get_drawing_report", {"report_id": report_id}))
    top = cast("list[Doc]", data["top_failures"])
    failures = cast("list[Doc]", worst_report()["failures"])
    assert len(top) == 5  # noqa: PLR2004
    for shown, original in zip(top, failures, strict=False):
        assert set(shown) == {"check", "sheet", "code", "items"}
        assert shown["check"] == original["check"]
        assert shown["code"] == original.get("code")
        items = cast("list[str]", shown["items"])
        assert items == [i["id"] for i in cast("list[Doc]", original["items"])][:3]
    assert data["execution_id"] == job_id
    assert data["job_warnings"] == [
        {"code": "solidworks_version_warning", "message": "Service pack older than SP3."}
    ]


@pytest.mark.parametrize("builder", [worst_report, unevaluated_report])
def test_report_summary_within_600_tokens(builder: Callable[[], Doc]) -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, builder())
    result = rig.call("get_drawing_report", {"report_id": report_id})
    data = ToolRig.data_of(result)
    size = len(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    assert size // BYTES_PER_TOKEN <= TOKEN_BUDGET
    assert data["warning_count"] == WARNINGS
    assert data["conflict_count"] == FAILURES
    assert len(cast("list[JsonValue]", data["top_failures"])) == 5  # noqa: PLR2004


def test_report_full_adds_checks_sheets_thresholds(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = commit_job(rig)
    report = stored_report(rig, job_id)
    data = ToolRig.data_of(
        rig.call("get_drawing_report", {"execution_id": job_id, "detail": "full"})
    )
    assert set(data) == SUMMARY_KEYS | {"sheets", "thresholds"}
    assert data["checks"] == report["checks"]
    assert data["sheets"] == report["sheets"]
    assert data["thresholds"] == report["thresholds"]
    assert "failures" not in data
    assert "warnings" not in data


# --- arguments ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"detail": "full"},
        {
            "report_id": "rep_00000000000000000000000001",
            "execution_id": "job_00000000000000000000000001",
        },
        {"report_id": "job_00000000000000000000000001"},
        {"execution_id": "rep_00000000000000000000000001"},
        {"report_id": "snap_00000000000000000000000001"},
        {"report_id": "rep_00000000000000000000000001".lower().replace("0", "i", 1)},
        {"report_id": "rep_0000000000000000000000001"},
        {"report_id": "rep_00000000000000000000000001\n"},
        {"report_id": "rep_" + "\u0660" * 26},
        {"report_id": None},
        {"report_id": 5},
        {"execution_id": ["job_00000000000000000000000001"]},
        {"report_id": UNKNOWN_REPORT, "detail": "everything"},
        {"report_id": UNKNOWN_REPORT, "detail": None},
        {"report_id": UNKNOWN_REPORT, "section": "failures"},
        {"report_id": UNKNOWN_REPORT, "section": 5},
        {"report_id": UNKNOWN_REPORT, "page_size": 10},
        {"report_id": UNKNOWN_REPORT, "cursor": "abc"},
        {"report_id": UNKNOWN_REPORT, "section": "checks", "cursor": "abc"},
        {"report_id": UNKNOWN_REPORT, "section": "soft_metrics", "page_size": 10},
        {"report_id": UNKNOWN_REPORT, "detail": "summary", "page_size": 10},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": 0},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": -1},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": 201},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": 10**30},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": 10.5},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": 10.0},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": "10"},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": True},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "page_size": None},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "cursor": 5},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "cursor": None},
        {"report_id": UNKNOWN_REPORT, "section": "conflicts", "cursor": ["a"]},
    ],
)
def test_get_drawing_report_bad_arguments_are_schema_invalid(arguments: JsonValue) -> None:
    rig = make_tool_rig()
    assert ToolRig.code_of(rig.call("get_drawing_report", arguments)) == "IR_SCHEMA_INVALID"


def test_report_id_xor_execution_id() -> None:
    rig = make_tool_rig()
    neither = rig.call("get_drawing_report", {})
    both = rig.call(
        "get_drawing_report", {"report_id": UNKNOWN_REPORT, "execution_id": UNKNOWN_JOB}
    )
    assert ToolRig.code_of(neither) == "IR_SCHEMA_INVALID"
    assert ToolRig.code_of(both) == "IR_SCHEMA_INVALID"
    assert (
        ToolRig.code_of(rig.call("get_drawing_report", {"report_id": UNKNOWN_REPORT}))
        == "EXEC_NOT_FOUND"
    )
    assert (
        ToolRig.code_of(rig.call("get_drawing_report", {"execution_id": UNKNOWN_JOB}))
        == "EXEC_NOT_FOUND"
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"cursor": "abc"},
        {"page_size": 10},
        {"section": "checks", "cursor": "abc"},
        {"section": "checks", "page_size": 10},
        {"section": "soft_metrics", "page_size": 10},
    ],
)
def test_cursor_requires_paginated_section(extra: Doc) -> None:
    rig = make_tool_rig()
    arguments: Doc = {"report_id": UNKNOWN_REPORT, **extra}
    assert ToolRig.code_of(rig.call("get_drawing_report", arguments)) == "IR_SCHEMA_INVALID"


# --- jobs without a report, and lookups that fail ------------------------------------------


def test_report_for_unfinished_job_has_null_report_id() -> None:
    rig = make_tool_rig()
    rig.write_drawing(DRAWING)
    job_id = str(ToolRig.data_of(rig.call("check_drawing", {"path": DRAWING}))["execution_id"])
    data = ToolRig.data_of(rig.call("get_drawing_report", {"execution_id": job_id}))
    assert data == {"execution_id": job_id, "state": "PLANNED", "report_id": None}


def test_report_for_failed_job_never_exists() -> None:
    unavailable = BackendUnavailable("BACKEND_LOST", "gone")
    rig = make_tool_rig(unavailable=unavailable, hello=make_hello())
    rig.write_drawing(DRAWING)
    job_id = str(ToolRig.data_of(rig.call("check_drawing", {"path": DRAWING}))["execution_id"])
    assert rig.rig.engine.run_next()
    data = ToolRig.data_of(
        rig.call("get_drawing_report", {"execution_id": job_id, "section": "conflicts"})
    )
    assert data == {"execution_id": job_id, "state": "FAILED", "report_id": None}


def test_report_for_aborted_job_never_exists() -> None:
    rig = make_tool_rig()
    rig.write_drawing(DRAWING)
    job_id = str(ToolRig.data_of(rig.call("check_drawing", {"path": DRAWING}))["execution_id"])
    rig.call("cancel_execution", {"execution_id": job_id})
    data = ToolRig.data_of(rig.call("get_drawing_report", {"execution_id": job_id}))
    assert data == {"execution_id": job_id, "state": "ABORTED", "report_id": None}


def test_expired_report_is_exec_not_found(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = commit_job(rig)
    report_id = rig.rig.job(job_id).report_id
    assert report_id is not None
    rig.rig.store().delete_report(report_id)
    result = rig.call("get_drawing_report", {"report_id": report_id})
    assert ToolRig.code_of(result) == "EXEC_NOT_FOUND"
    by_job = rig.call("get_drawing_report", {"execution_id": job_id})
    assert ToolRig.code_of(by_job) == "EXEC_NOT_FOUND"


def test_corrupt_report_file_is_store_corrupt(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = commit_job(rig)
    report_id = rig.rig.job(job_id).report_id
    rig.rig.fs.write_atomic(f"{STORE_DIR}\\reports\\{report_id}.json", b"{broken")
    result = rig.call("get_drawing_report", {"report_id": report_id})
    assert ToolRig.code_of(result) == "STORE_CORRUPT"


@pytest.mark.parametrize("stored", [{}, {"verdict": "fail"}, {"checks": 5, "verdict": 1}, []])
def test_structurally_wrong_report_is_store_corrupt(stored: JsonValue) -> None:
    rig = make_tool_rig()
    store = rig.rig.store()
    ids = rig.rig.ids
    drawing_id, snapshot_id = ids.new_id("drw"), ids.new_id("snap")
    report_id, job_id = ids.new_id("rep"), ids.new_id("job")
    now = store.timestamp()
    store.put_drawing(
        DrawingRecord(drawing_id, DRAWING, FINGERPRINT, False, None, snapshot_id, report_id, now)
    )
    store.put_report(
        report_id, stored, ReportMeta(report_id, job_id, drawing_id, snapshot_id, now, ())
    )
    variants: list[Doc] = [
        {"report_id": report_id},
        {"report_id": report_id, "detail": "full"},
        {"report_id": report_id, "section": "checks"},
        {"report_id": report_id, "section": "conflicts"},
    ]
    for arguments in variants:
        assert ToolRig.code_of(rig.call("get_drawing_report", arguments)) == "STORE_CORRUPT"


# --- ids and summary lines ----------------------------------------------------------------


def test_report_ids_name_the_report_and_the_job(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = commit_job(rig)
    report_id = rig.rig.job(job_id).report_id
    ids = ToolRig.ids_of(rig.call("get_drawing_report", {"report_id": report_id}))
    assert set(ids) == {"request_id", "execution_id", "report_id"}
    assert ids["report_id"] == report_id
    assert ids["execution_id"] == job_id
    pending = ToolRig.ids_of(rig.call("get_drawing_report", {"execution_id": UNKNOWN_JOB}))
    assert set(pending) == {"request_id", "execution_id"}


def test_report_summary_lines(failing_snapshot: Doc, good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=failing_snapshot)
    job_id = commit_job(rig)
    report_id = rig.rig.job(job_id).report_id
    report = stored_report(rig, job_id)
    checks = cast("dict[str, Doc]", report["checks"])
    failed = ", ".join(
        f"{n} \u00d7{c['failure_count']}" for n, c in checks.items() if c["status"] == "fail"
    )
    result = rig.call("get_drawing_report", {"execution_id": job_id})
    assert result.summary == f"drawing check FAIL: {failed} (report {report_id})"

    other = make_tool_rig(snapshot=good_snapshot)
    other_job = commit_job(other)
    other_report = stored_report(other, other_job)
    assert other_report["verdict"] == "not_evaluated"
    names = ", ".join(
        n
        for n, c in cast("dict[str, Doc]", other_report["checks"]).items()
        if c["status"] == "not_evaluated"
    )
    other_id = other.rig.job(other_job).report_id
    summary = other.call("get_drawing_report", {"execution_id": other_job}).summary
    assert summary == f"drawing check NOT EVALUATED: {names} (report {other_id})"

    done = base_report()
    for check in cast("dict[str, Doc]", done["checks"]).values():
        check.update(status="pass", failure_count=0, reasons=[])
    done["verdict"] = "done"
    done_id, _ = seed_report(other, done)
    assert other.call("get_drawing_report", {"report_id": done_id}).summary == (
        f"drawing check DONE (report {done_id})"
    )


def test_worst_case_summary_line_fits_200_characters() -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, worst_report())
    result = rig.call("get_drawing_report", {"report_id": report_id})
    assert result.summary.startswith("drawing check FAIL: D1 \u00d7200")
    assert len(result.summary) <= 200  # noqa: PLR2004
