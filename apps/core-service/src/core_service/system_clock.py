"""Real time behind the ``Clock`` port (ADR-053)."""

import threading
import time
from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic_s(self) -> float:
        return time.monotonic()

    def wait(self, cond: threading.Condition, timeout_s: float) -> None:
        """Wait on ``cond`` (held by the caller) for at most ``timeout_s``."""
        cond.wait(max(0.0, timeout_s))
