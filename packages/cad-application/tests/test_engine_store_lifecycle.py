"""When the engine recovers and cleans a store (spec 13.2.3 edge cases, 13.2.4; register J18)."""

from datetime import UTC, datetime

from cad_application.store.job_records import JobRecord
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.job_rig import KNOWN_STORES, Rig, make_rig
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]

LATER = datetime(2027, 11, 5, tzinfo=UTC)


def _finished_job(good_snapshot: Doc) -> tuple[Rig, str]:
    rig = make_rig(snapshot=good_snapshot)
    job = rig.submit()
    assert rig.engine.run_next()
    assert rig.job(job.job_id).state == "COMMITTED"
    rig.stores.close_all()
    return rig, job.job_id


def test_clean_up_runs_at_start(good_snapshot: Doc) -> None:
    rig, job_id = _finished_job(good_snapshot)
    restarted = make_rig(fs=rig.fs, clock=FakeClock(LATER))
    restarted.engine.recover_all()
    assert restarted.store().get_job(job_id) is None  # past the retention, deleted at start


def test_clean_up_all_is_callable_for_the_daily_run(good_snapshot: Doc) -> None:
    rig, job_id = _finished_job(good_snapshot)
    clock = FakeClock()
    restarted = make_rig(fs=rig.fs, clock=clock)
    restarted.engine.recover_all()
    assert isinstance(restarted.store().get_job(job_id), JobRecord)
    clock.advance((LATER - datetime(2026, 11, 4, tzinfo=UTC)).total_seconds())
    restarted.engine.clean_up_all()
    assert restarted.store().get_job(job_id) is None


def test_unlisted_store_recovered_on_first_open() -> None:
    rig = make_rig()
    queued = rig.submit()
    rig.stores.close_all()
    rig.fs.remove(KNOWN_STORES)  # an unreadable or lost list: nothing is opened at start
    restarted = make_rig(fs=rig.fs, clock=FakeClock(datetime(2026, 11, 5, tzinfo=UTC)))
    assert restarted.engine.recover_all() == ()
    assert restarted.engine.status(queued.job_id) is None  # not visible before its recovery
    restarted.ids.new_id("job")  # a restarted rig reuses IDs: keep the new job's apart
    restarted.submit()  # the first open of the store
    view = restarted.engine.status(queued.job_id)
    assert view is not None
    assert view.state == "ABORTED"
