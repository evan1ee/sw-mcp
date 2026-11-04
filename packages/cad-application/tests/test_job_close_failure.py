"""A drawing the job could not close is listed as unknown (8.4, J17)."""

from cad_application.ports import BackendCallError
from cad_application.store.job_records import JobDocument
from cad_application.testing.job_rig import DRAWING, make_rig
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]

CLOSE_BATCH = 2


def test_failed_close_marks_unknown(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    sent: list[str] = []

    def fail_second_batch(name: str) -> None:
        if name == "apply_ops":
            sent.append(name)
            if len(sent) == CLOSE_BATCH:  # the open is the first batch, the close the second
                raise BackendCallError("BACKEND_BUSY", "SOLIDWORKS is busy.")

    rig.backend.before = fail_second_batch
    job = rig.submit()
    assert rig.engine.run_next()
    record = rig.job(job.job_id)
    assert record.state == "COMMITTED"  # a failed close never changes the outcome
    assert record.documents == (JobDocument(DRAWING, True, "unknown"),)
    assert [w.code for w in record.warnings] == ["drawing_close_failed"]
    failed = [e for e in rig.log.events if e.event == "job.close_failed"]
    assert [e.fields["reason"] for e in failed] == ["JobStop"]
