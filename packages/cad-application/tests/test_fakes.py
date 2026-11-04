"""The shared test doubles: IDs, event log and FakeBackend."""

import threading

import pytest
from cad_application.ids import is_id
from cad_application.ports import Backend, BackendCallError
from cad_application.testing.fakes import FakeBackend, ListEventLog, SequentialIdSource, make_hello
from cad_ir.generated.ipc import Meta, Operation, OperationGroup

PATH = "C:\\w\\a.SLDDRW"
GUARD_S = 5.0


def test_sequential_ids_are_valid_and_distinct() -> None:
    ids = SequentialIdSource()
    first, second, report = ids.new_id("job"), ids.new_id("job"), ids.new_id("rep")
    assert is_id(first, "job")
    assert is_id(report, "rep")
    assert first < second
    assert first.endswith("1")
    assert report.endswith("1")


def test_list_event_log_records_events() -> None:
    log = ListEventLog()
    log.emit("job.state", "info", job_id="job_x", count=2)
    assert [(e.event, e.level, dict(e.fields)) for e in log.events] == [
        ("job.state", "info", {"job_id": "job_x", "count": 2})
    ]


def _open_group(op_id: str) -> OperationGroup:
    op = Operation(operation_id=op_id, op="document.open", params={"path": PATH})
    return OperationGroup(document=PATH, operations=(op,))


def test_fake_backend_records_and_answers() -> None:
    backend: Backend = FakeBackend(make_hello(), snapshot={"s": 1}, open_owned=False)
    meta = Meta(request_id="req_1", job_id="job_1", operation_id="job_1:1")
    result = backend.apply_ops((_open_group("job_1:1"),), meta=meta)
    assert result.outcomes[0].result == {"owned": False}
    assert backend.completed_operations() == ("job_1:1",)
    assert backend.snapshot_drawing(PATH, None, meta=meta) == {"s": 1}
    assert isinstance(backend, FakeBackend)
    assert [c.name for c in backend.calls] == ["apply_ops", "snapshot_drawing"]
    assert backend.calls[0].meta == meta


def test_fake_backend_blocked_snapshot_is_cancelled() -> None:
    block = threading.Event()
    backend = FakeBackend(make_hello(), block=block)
    outcome: list[object] = []

    def work() -> None:
        try:
            outcome.append(backend.snapshot_drawing(PATH))
        except BackendCallError as error:
            outcome.append(error)

    thread = threading.Thread(target=work)
    thread.start()
    assert backend.snapshot_started.wait(GUARD_S)
    assert backend.cancel() is True
    thread.join(GUARD_S)
    assert not thread.is_alive()
    assert isinstance(outcome[0], BackendCallError)
    assert outcome[0].code == "EXEC_CANCELLED"


def test_fake_backend_released_block_returns_snapshot() -> None:
    block = threading.Event()
    block.set()
    backend = FakeBackend(make_hello(), snapshot={"ok": True}, block=block)
    assert backend.snapshot_drawing(PATH) == {"ok": True}


def test_backend_call_error_carries_code() -> None:
    with pytest.raises(BackendCallError) as info:
        raise BackendCallError("BACKEND_LOST", "gone", {"x": 1})
    assert (info.value.code, info.value.message, info.value.details) == (
        "BACKEND_LOST",
        "gone",
        {"x": 1},
    )
