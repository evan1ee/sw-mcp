"""get_drawing_report sections and cursors (spec 12.4.5, 12.4.2)."""

from datetime import timedelta
from typing import cast

import pytest
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.report_rig import (
    FAILURES,
    WARNINGS,
    commit_job,
    seed_report,
    stored_report,
    worst_report,
)
from cad_application.testing.tool_rig import ToolRig, make_tool_rig
from cad_application.tools.cursor import encode_cursor
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]

DEFAULT_PAGE = 50
UNKNOWN_JOB = "job_00000000000000000000000077"


# --- sections -----------------------------------------------------------------------------


def test_report_sections_checks_and_soft_metrics_whole(good_snapshot: Doc) -> None:
    rig = make_tool_rig(snapshot=good_snapshot)
    job_id = commit_job(rig)
    report = stored_report(rig, job_id)
    report_id = rig.rig.job(job_id).report_id
    for section, key in (("checks", "checks"), ("soft_metrics", "sheets")):
        data = ToolRig.data_of(
            rig.call("get_drawing_report", {"report_id": report_id, "section": section})
        )
        assert data == {"report_id": report_id, "section": section, "items": report[key]}


def test_section_ignores_detail() -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, worst_report())
    plain = rig.call("get_drawing_report", {"report_id": report_id, "section": "checks"})
    full = rig.call(
        "get_drawing_report", {"report_id": report_id, "section": "checks", "detail": "full"}
    )
    assert ToolRig.data_of(plain) == ToolRig.data_of(full)


@pytest.mark.parametrize(
    ("section", "key", "total"),
    [("conflicts", "failures", FAILURES), ("warnings", "warnings", WARNINGS)],
)
def test_report_sections_paginate(section: str, key: str, total: int) -> None:
    rig = make_tool_rig()
    report = worst_report()
    report_id, _ = seed_report(rig, report)
    collected: list[JsonValue] = []
    arguments: Doc = {"report_id": report_id, "section": section}
    pages = 0
    while True:
        data = ToolRig.data_of(rig.call("get_drawing_report", arguments))
        assert set(data) <= {"report_id", "section", "items", "next_cursor"}
        items = cast("list[JsonValue]", data["items"])
        assert 0 < len(items) <= DEFAULT_PAGE
        collected.extend(items)
        pages += 1
        cursor = data.get("next_cursor")
        if cursor is None:
            break
        arguments = {**arguments, "cursor": cursor}
    assert collected == report[key]
    assert pages == -(-total // DEFAULT_PAGE)


def test_page_size_is_honoured_and_part_of_the_cursor() -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, worst_report())
    base: Doc = {"report_id": report_id, "section": "conflicts", "page_size": 7}
    first = ToolRig.data_of(rig.call("get_drawing_report", base))
    assert len(cast("list[JsonValue]", first["items"])) == 7  # noqa: PLR2004
    cursor = first["next_cursor"]
    second = ToolRig.data_of(rig.call("get_drawing_report", {**base, "cursor": cursor}))
    failures = cast("list[JsonValue]", worst_report()["failures"])
    assert second["items"] == failures[7:14]
    changed = rig.call("get_drawing_report", {**base, "page_size": 8, "cursor": cursor})
    assert ToolRig.code_of(changed) == "IR_SCHEMA_INVALID"


def test_cursor_for_other_section_or_report_is_rejected() -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, worst_report())
    other_id, _ = seed_report(rig, worst_report())
    first = ToolRig.data_of(
        rig.call("get_drawing_report", {"report_id": report_id, "section": "conflicts"})
    )
    cursor = first["next_cursor"]
    for arguments in (
        {"report_id": report_id, "section": "warnings", "cursor": cursor},
        {"report_id": other_id, "section": "conflicts", "cursor": cursor},
    ):
        assert ToolRig.code_of(rig.call("get_drawing_report", arguments)) == "IR_SCHEMA_INVALID"


def test_cursor_from_another_tool_is_rejected() -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, worst_report())
    foreign = rig.call("check_drawing", {"path": "C:\\Work\\none.slddrw"})
    assert ToolRig.code_of(foreign) == "FILE_NOT_FOUND"
    cursor = encode_cursor(0, 0, {"execution_id": UNKNOWN_JOB})
    result = rig.call(
        "get_drawing_report", {"report_id": report_id, "section": "conflicts", "cursor": cursor}
    )
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"


def test_cursor_expires_after_ten_minutes_of_clock_time() -> None:
    clock = FakeClock()
    rig = make_tool_rig(clock=clock)
    report_id, _ = seed_report(rig, worst_report())
    arguments: Doc = {"report_id": report_id, "section": "conflicts"}
    cursor = ToolRig.data_of(rig.call("get_drawing_report", arguments))["next_cursor"]
    clock.advance(timedelta(minutes=10).total_seconds() - 0.001)
    live = rig.call("get_drawing_report", {**arguments, "cursor": cursor})
    assert ToolRig.code_of(live) is None
    clock.advance(0.001)
    gone = rig.call("get_drawing_report", {**arguments, "cursor": cursor})
    assert ToolRig.code_of(gone) == "IR_SCHEMA_INVALID"


def test_cursor_past_the_end_gives_an_empty_last_page() -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, worst_report())
    arguments: Doc = {"report_id": report_id, "section": "warnings"}
    cursor = encode_cursor(10**9, int(rig.rig.clock.now().timestamp() * 1000), arguments)
    data = ToolRig.data_of(rig.call("get_drawing_report", {**arguments, "cursor": cursor}))
    assert data["items"] == []
    assert "next_cursor" not in data


def test_section_summary_line() -> None:
    rig = make_tool_rig()
    report_id, _ = seed_report(rig, worst_report())
    result = rig.call("get_drawing_report", {"report_id": report_id, "section": "conflicts"})
    assert result.summary == f"report {report_id} conflicts: 50 of 200 items"
