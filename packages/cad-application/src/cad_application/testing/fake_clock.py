"""A clock that moves only when told to (ADR-053)."""

import threading
from datetime import UTC, datetime, timedelta

_START = datetime(2026, 11, 4, 9, 0, 0, tzinfo=UTC)


class FakeClock:
    """``wait`` advances time by the timeout and returns at once, so no test waits for real."""

    def __init__(self, start: datetime = _START) -> None:
        self._start = start
        self._elapsed_s = 0.0
        self._guard = threading.Lock()

    def now(self) -> datetime:
        with self._guard:
            return self._start + timedelta(seconds=self._elapsed_s)

    def monotonic_s(self) -> float:
        with self._guard:
            return self._elapsed_s

    def advance(self, seconds: float) -> None:
        with self._guard:
            self._elapsed_s += seconds

    def wait(self, cond: threading.Condition, timeout_s: float) -> None:
        """Called with ``cond`` held; time passes, nothing blocks."""
        del cond
        self.advance(timeout_s)
