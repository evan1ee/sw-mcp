"""SystemClock and SystemIdSource: real time and randomness behind the Clock and IdSource ports."""

import threading

from cad_application.ids import ID_PREFIXES, is_id
from core_service.system_clock import SystemClock
from core_service.system_ids import SystemIdSource


def test_system_clock_is_aware_utc_and_monotonic() -> None:
    clock = SystemClock()
    first, second = clock.monotonic_s(), clock.monotonic_s()
    assert second >= first
    assert clock.now().utcoffset() is not None
    assert clock.now().utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_system_clock_wait_returns_when_notified() -> None:
    clock = SystemClock()
    cond = threading.Condition()
    started = threading.Event()
    returned = threading.Event()

    def waiter() -> None:
        with cond:
            started.set()
            clock.wait(cond, 5.0)
        returned.set()

    thread = threading.Thread(target=waiter)
    thread.start()
    assert started.wait(5.0)
    with cond:  # only acquired once the waiter is inside wait(), which releases it
        cond.notify_all()
    assert returned.wait(5.0)
    thread.join(5.0)
    assert not thread.is_alive()


def test_system_ids_are_valid_for_every_prefix() -> None:
    ids = SystemIdSource()
    for prefix in ID_PREFIXES:
        assert is_id(ids.new_id(prefix), prefix)


def test_system_ids_are_unique_and_increasing() -> None:
    ids = SystemIdSource()
    made = [ids.new_id("job") for _ in range(2000)]
    assert len(set(made)) == len(made)
    assert made == sorted(made)


def test_system_ids_are_unique_across_threads() -> None:
    ids = SystemIdSource()
    bucket: list[str] = []
    guard = threading.Lock()

    def work() -> None:
        mine = [ids.new_id("req") for _ in range(500)]
        with guard:
            bucket.extend(mine)

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5.0)
    assert len(bucket) == 2000  # noqa: PLR2004
    assert len(set(bucket)) == len(bucket)
