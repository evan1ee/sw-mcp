"""A snapshot is validated before it is stored (13.2.3 edge cases, 8.4)."""

import copy

import pytest
from cad_application.store.journal_records import StateRecord
from cad_application.testing.job_rig import make_rig
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]

VALIDATION_CODES = {"IR_SCHEMA_INVALID", "IR_RULE_VIOLATED"}


def _with_scale(doc: Doc, value: JsonValue) -> Doc:
    changed = copy.deepcopy(doc)
    sheets = changed["sheets"]
    assert isinstance(sheets, dict)
    sheet = sheets["s_0123456789"]
    assert isinstance(sheet, dict)
    views = sheet["views"]
    assert isinstance(views, dict)
    view = views["v_front"]
    assert isinstance(view, dict)
    view["scale"] = value
    return changed


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 10**500], ids=["nan", "inf", "big"])
def test_nan_snapshot_not_stored(good_snapshot: Doc, value: JsonValue) -> None:
    rig = make_rig(snapshot=_with_scale(good_snapshot, value))
    job = rig.submit()
    assert rig.engine.run_next()
    record = rig.job(job.job_id)
    assert record.state == "FAILED"
    assert record.error is not None
    assert record.error["code"] in VALIDATION_CODES
    assert record.snapshot_id is None
    assert record.report_id is None
    assert rig.fs.stat(
        "C:" + chr(92) + "Work" + chr(92) + ".cad" + chr(92) + "snapshots"
    ) is None or (
        rig.fs.list_dir("C:" + chr(92) + "Work" + chr(92) + ".cad" + chr(92) + "snapshots") == ()
    )
    last = [r for r in rig.journal(job.job_id) if isinstance(r, StateRecord)][-1]
    assert (last.from_state, last.to) == ("EXECUTING", "FAILED")
