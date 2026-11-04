"""FakeClock: time moves only when told to, and waiting never blocks (ADR-053)."""

import threading
from datetime import UTC, datetime, timedelta

from cad_application.ports import Clock
from cad_application.testing.fake_clock import FakeClock


def test_fake_clock_is_a_clock_in_utc() -> None:
    clock: Clock = FakeClock()
    assert clock.now().tzinfo is UTC


def test_fake_clock_wait_advances_without_blocking() -> None:
    clock = FakeClock(start=datetime(2026, 11, 4, 9, 0, tzinfo=UTC))
    cond = threading.Condition()
    before = clock.monotonic_s()
    with cond:
        clock.wait(cond, 2.5)
    assert clock.monotonic_s() == before + 2.5
    assert clock.now() == datetime(2026, 11, 4, 9, 0, 2, 500000, tzinfo=UTC)


def test_fake_clock_advance_moves_both_readings() -> None:
    clock = FakeClock()
    start_now, start_mono = clock.now(), clock.monotonic_s()
    clock.advance(600)
    assert clock.now() - start_now == timedelta(seconds=600)
    assert clock.monotonic_s() - start_mono == 600  # noqa: PLR2004
