"""Which document events fail a job (8.4 'Events the job caused', J16)."""

from cad_application.testing.job_rig import DRAWING, make_rig
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]


def test_document_event_from_other_job_interrupts(good_snapshot: Doc) -> None:
    rig = make_rig(snapshot=good_snapshot)
    other: Doc = {"job_id": "job_000000000000000000000000ZZ"}

    def after(name: str) -> None:
        if name == "snapshot_drawing":
            rig.provider.notify(
                "document.event", {"document": DRAWING, "event": "regen", "_meta": other}
            )

    rig.backend.after = after
    job = rig.submit()
    assert rig.engine.run_next()
    record = rig.job(job.job_id)
    assert record.state == "FAILED"
    assert record.error is not None
    assert record.error["code"] == "EXEC_INTERRUPTED_BY_USER"
