"""Step 2 of start-up recovery (13.2.3), done on the first backend connection."""

import threading
from collections.abc import Callable

from cad_application.jobs.engine import JobEngine
from cad_application.ports import Backend, BackendProvider
from cad_ir.core.json_types import JsonValue


class ReconcilingProvider:
    """While a recovery has left unanswered operations, ``acquire`` asks the add-in
    which operations it completed and records them (``JobEngine.reconcile``). A failure of that
    call fails the ``acquire``, so the job reports it, and the next ``acquire`` tries again."""

    def __init__(self, inner: BackendProvider) -> None:
        self._inner = inner
        self._guard = threading.Lock()
        self._engine: JobEngine | None = None

    def arm(self, engine: JobEngine) -> None:
        with self._guard:
            self._engine = engine

    def acquire(self, on_notification: Callable[[str, JsonValue], None]) -> Backend:
        backend = self._inner.acquire(on_notification)
        with self._guard:
            if self._engine is not None and self._engine.reconcile_pending():
                self._engine.reconcile(backend)
        return backend
