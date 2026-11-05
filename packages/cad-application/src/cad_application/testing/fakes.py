"""Test doubles: IDs, event log and a scriptable backend (guideline G2)."""

import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import (
    HelloResult,
    Meta,
    OperationGroup,
    OperationInfo,
    OperationOutcome,
    OpsApplyResult,
    SolidWorksInfo,
)

from cad_application.ids import IdPrefix, encode_ulid
from cad_application.ports import Backend, BackendCallError, BackendUnavailable, LogValue

_RANDOM_BYTES: Final = 10
_GUARD_S: Final = 5.0


def make_hello(
    *,
    warnings: Sequence[str] = (),
    capabilities: Sequence[str] = ("drawing.snapshot", "ops.apply"),
    operations: Sequence[str] = ("document.open", "document.close"),
) -> HelloResult:
    """A handshake result for tests."""
    return HelloResult(
        protocol="0.1",
        addin_version="0.1.0",
        solidworks=SolidWorksInfo(version="2025", service_pack="SP3.0", ui_language="en-US"),
        capabilities=tuple(capabilities),
        operations=tuple(OperationInfo(op=op, schema_version="0.1") for op in operations),
        licensed_modules=(),
        warnings=tuple(warnings),
    )


class SequentialIdSource:
    """``job_00000000000000000000000001``, ``job_...2``, then the same per prefix."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._guard = threading.Lock()

    def new_id(self, prefix: IdPrefix) -> str:
        with self._guard:
            self._counts[prefix] += 1
            number = self._counts[prefix]
        return f"{prefix}_{encode_ulid(0, number.to_bytes(_RANDOM_BYTES, 'big'))}"


@dataclass(frozen=True, slots=True)
class LoggedEvent:
    event: str
    level: str
    fields: Mapping[str, LogValue]


class ListEventLog:
    """Keeps every event in memory."""

    def __init__(self) -> None:
        self.events: list[LoggedEvent] = []
        self._guard = threading.Lock()

    def emit(self, event: str, level: str, **fields: LogValue) -> None:
        with self._guard:
            self.events.append(LoggedEvent(event, level, dict(fields)))


@dataclass(frozen=True, slots=True)
class RecordedCall:
    name: str
    meta: Meta | None
    args: tuple[object, ...]


class FakeBackend:
    """A Backend that records calls and answers from its settings.

    ``snapshot_drawing`` waits on ``block`` when given (``snapshot_started`` tells a test the
    worker is waiting), and raises ``BackendCallError("EXEC_CANCELLED")`` when ``cancel()`` was
    called meanwhile. It raises only this package's own error type, never an IPC type.

    ``before`` and ``after`` are settable attributes. ``before`` runs at the start of every call
    (it may raise to script a failure) and ``after`` just before the result is returned; both
    receive the method name.
    """

    def __init__(  # noqa: PLR0913 - one knob per scripted behaviour
        self,
        session: HelloResult,
        *,
        snapshot: JsonValue = None,
        measurement: JsonValue | Callable[[str], JsonValue] = None,
        op_results: Mapping[str, JsonValue] | None = None,
        open_owned: bool = True,
        block: threading.Event | None = None,
        before: Callable[[str], None] | None = None,
        after: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self.before = before
        self.after = after
        self._snapshot: JsonValue = {} if snapshot is None else snapshot
        self._measurement = measurement
        self._op_results = op_results
        self._open_owned = open_owned
        self._block = block
        self._completed: list[str] = []
        self._cancelled = threading.Event()
        self.calls: list[RecordedCall] = []
        self.snapshot_started = threading.Event()
        self.closed = False

    @property
    def session(self) -> HelloResult:
        return self._session

    @property
    def cancel_called(self) -> bool:
        return self._cancelled.is_set()

    def snapshot_drawing(
        self, document: str, sheets: Sequence[str] | None = None, *, meta: Meta | None = None
    ) -> JsonValue:
        self.calls.append(RecordedCall("snapshot_drawing", meta, (document, sheets)))
        self._run_hook(self.before, "snapshot_drawing")
        if self._block is not None:
            self.snapshot_started.set()
            self._block.wait(_GUARD_S)
        if self._cancelled.is_set():
            raise BackendCallError("EXEC_CANCELLED", "The command was cancelled.")
        self._run_hook(self.after, "snapshot_drawing")
        return self._snapshot

    def measure_part(self, document: str, *, meta: Meta | None = None) -> JsonValue:
        self.calls.append(RecordedCall("measure_part", meta, (document,)))
        self._run_hook(self.before, "measure_part")
        if self._cancelled.is_set():
            raise BackendCallError("EXEC_CANCELLED", "The command was cancelled.")
        self._run_hook(self.after, "measure_part")
        if callable(self._measurement):
            return self._measurement(document)
        if isinstance(self._measurement, dict) and document in self._measurement:
            return cast(JsonValue, self._measurement[document])
        return self._measurement

    @staticmethod
    def _run_hook(hook: Callable[[str], None] | None, name: str) -> None:
        if hook is not None:
            hook(name)

    def apply_ops(
        self, groups: Sequence[OperationGroup], *, meta: Meta | None = None
    ) -> OpsApplyResult:
        self.calls.append(RecordedCall("apply_ops", meta, (tuple(groups),)))
        self._run_hook(self.before, "apply_ops")
        outcomes: list[OperationOutcome] = []
        for group in groups:
            for operation in group.operations:
                self._completed.append(operation.operation_id)
                result: JsonValue = {}
                if self._op_results is not None and operation.operation_id in self._op_results:
                    result = self._op_results[operation.operation_id]
                elif self._op_results is not None and operation.op in self._op_results:
                    result = self._op_results[operation.op]
                elif operation.op == "document.open":
                    result = {"owned": self._open_owned}
                elif operation.op == "document.close":
                    result = {"closed": True}
                outcomes.append(
                    OperationOutcome(operation_id=operation.operation_id, result=result)
                )
        self._run_hook(self.after, "apply_ops")
        return OpsApplyResult(outcomes=tuple(outcomes))

    def completed_operations(self) -> tuple[str, ...]:
        return tuple(self._completed)

    def cancel(self, *, meta: Meta | None = None) -> bool:
        self.calls.append(RecordedCall("cancel", meta, ()))
        self._cancelled.set()
        if self._block is not None:
            self._block.set()
        return True

    def close(self) -> None:
        self.closed = True
        self.calls.append(RecordedCall("close", None, ()))


class FakeBackendProvider:
    """Hands out one backend, or raises ``BackendUnavailable``. ``notify`` plays a notification
    of the session to the callback of the latest ``acquire``."""

    def __init__(self, backend: Backend | None, error: BackendUnavailable | None = None) -> None:
        self.backend = backend
        self.error = error
        self.acquired = 0
        self._callback: Callable[[str, JsonValue], None] | None = None

    def acquire(self, on_notification: Callable[[str, JsonValue], None]) -> Backend:
        self.acquired += 1
        self._callback = on_notification
        if self.error is not None:
            raise self.error
        if self.backend is None:
            raise BackendUnavailable("BACKEND_LOST", "No SOLIDWORKS session.")
        return self.backend

    def notify(self, method: str, params: JsonValue) -> None:
        if self._callback is not None:
            self._callback(method, params)
