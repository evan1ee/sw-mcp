"""The IPC client (spec 8.7): requests, notifications, chunks, timeouts and pipe loss.

Single-threaded: whoever waits for a response reads frames and files each one under the call
it answers. A timeout reports ``EXEC_TIMEOUT``, never resends (8.3 rule 8), and forgets the
call, so its late response or chunks are discarded.
"""

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import (
    PROTOCOL_VERSION,
    CompletedOperationsParams,
    CompletedOperationsResult,
    HelloParams,
    HelloResult,
    JobCancelParams,
    JobCancelResult,
    Meta,
    Notification,
    OperationGroup,
    OpsApplyParams,
    OpsApplyResult,
    PingParams,
    PingResult,
    Request,
    ResponseChunkParams,
    SnapshotParams,
)
from cad_ir.generated.ipc import Response as RpcResponse

from cad_protocol.client import chunks
from cad_protocol.client.transport import Transport, TransportClosed, TransportTimeout
from cad_protocol.errors import INVALID_RESPONSE, IpcError, IpcProtocolFault

type NotificationHandler = Callable[[str, JsonValue], None]

_CATALOGUE_ERROR = -32000
_PARSE_ERROR = -32700


@dataclass(slots=True)
class CallState:
    """One request in flight; the client fills in ``response`` when it arrives."""

    id: int
    timeout_s: float
    deadline: float = 0.0
    response: RpcResponse | None = None


class PendingCall:
    """A request that is sent and not yet answered; ``wait`` returns its result."""

    def __init__(self, client: "IpcClient", call: CallState) -> None:
        self._client = client
        self._call = call

    @property
    def id(self) -> int:
        return self._call.id

    def wait(self) -> JsonValue:
        return self._client.await_result(self._call)


def _lost() -> IpcError:
    return IpcError("BACKEND_LOST", "The add-in closed the connection.", "after_fix")


def _major(version: str) -> str:
    return version.split(".", 1)[0]


class IpcClient:
    def __init__(  # noqa: PLR0913 - the plan's signature plus protocol
        self,
        transport: Transport,
        *,
        token: str,
        on_notification: NotificationHandler | None = None,
        read_timeout_s: float = 30.0,
        command_timeout_s: float = 120.0,
        protocol: str = PROTOCOL_VERSION,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._token = token
        self._on_notification = on_notification
        self._read_timeout_s = read_timeout_s
        self._command_timeout_s = command_timeout_s
        self._protocol = protocol
        self._monotonic = monotonic
        self._next_id = 1
        self._closed = False
        self._pending: dict[int, CallState] = {}
        self._partial: dict[int, chunks.Partial] = {}

    # --- public calls -------------------------------------------------------------------

    def hello(self) -> HelloResult:
        params = HelloParams(token=self._token, protocol=self._protocol)
        result = self._parse(HelloResult.from_json, self._call("session.hello", params.to_json()))
        if _major(result.protocol) != _major(self._protocol):
            self.close()
            raise IpcError(
                "BACKEND_VERSION_UNSUPPORTED",
                f"The add-in speaks protocol {result.protocol}, not {self._protocol}.",
                "never",
            )
        return result

    def ping(self) -> PingResult:
        reply = self._call("session.ping", PingParams().to_json())
        return self._parse(PingResult.from_json, reply)

    def completed_operations(self) -> tuple[str, ...]:
        params = CompletedOperationsParams().to_json()
        reply = self._call("session.completed_operations", params)
        return self._parse(CompletedOperationsResult.from_json, reply).operation_ids

    def begin_snapshot_drawing(
        self, document: str, sheets: Sequence[str] | None = None, *, meta: Meta | None = None
    ) -> PendingCall:
        """Send ``drawing.snapshot`` without waiting, so ``cancel`` can follow it."""
        params = SnapshotParams(
            document=document, sheets=None if sheets is None else tuple(sheets), meta=meta
        )
        return PendingCall(self, self._begin("drawing.snapshot", params.to_json(), "command"))

    def snapshot_drawing(
        self, document: str, sheets: Sequence[str] | None = None, *, meta: Meta | None = None
    ) -> JsonValue:
        return self.begin_snapshot_drawing(document, sheets, meta=meta).wait()

    def apply_ops(
        self, groups: Sequence[OperationGroup], *, meta: Meta | None = None
    ) -> OpsApplyResult:
        params = OpsApplyParams(groups=tuple(groups), meta=meta)
        call = self._begin("ops.apply", params.to_json(), "command")
        return self._parse(OpsApplyResult.from_json, self.await_result(call))

    def cancel(self, *, meta: Meta | None = None) -> bool:
        params = JobCancelParams(meta=meta).to_json()
        reply = self.await_result(self._begin("job.cancel", params, "command"))
        return self._parse(JobCancelResult.from_json, reply).cancelled

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._transport.close()

    # --- sending and waiting ------------------------------------------------------------

    def _call(self, method: str, params: JsonValue) -> JsonValue:
        return self.await_result(self._begin(method, params, "read"))

    def _begin(self, method: str, params: JsonValue, kind: str) -> CallState:
        if self._closed:
            raise _lost()
        timeout = self._command_timeout_s if kind == "command" else self._read_timeout_s
        call = CallState(self._next_id, timeout)
        self._next_id += 1
        frame = Request(id=call.id, method=method, params=params).to_json()
        try:
            self._transport.send(json.dumps(frame, ensure_ascii=False).encode("utf-8"))
        except TransportClosed:
            self._closed = True
            raise _lost() from None
        call.deadline = self._monotonic() + timeout
        self._pending[call.id] = call
        return call

    def await_result(self, call: CallState) -> JsonValue:
        while call.response is None:
            if self._closed:
                self._forget(call)
                raise _lost()
            self._pump(call)
        self._forget(call)
        return self._result_of(call.response)

    def _forget(self, call: CallState) -> None:
        self._pending.pop(call.id, None)
        self._partial.pop(call.id, None)

    def _pump(self, call: CallState) -> None:
        remaining = call.deadline - self._monotonic()
        if remaining <= 0:
            raise self._timed_out(call)
        try:
            payload = self._transport.receive(remaining)
        except TransportTimeout:
            raise self._timed_out(call) from None
        except TransportClosed:
            self._closed = True
            return
        self._dispatch(payload)

    def _timed_out(self, call: CallState) -> IpcError:
        self._forget(call)
        return IpcError(
            "EXEC_TIMEOUT",
            "The add-in did not answer in time; the request was not sent again.",
            "after_fix",
        )

    # --- incoming frames ----------------------------------------------------------------

    def _dispatch(self, payload: bytes) -> None:
        try:
            note = self._file(payload)
        except ValueError as exc:
            raise IpcProtocolFault(INVALID_RESPONSE, f"unusable frame: {exc}") from None
        if note is not None:  # outside the try: the caller's callback errors are not ours
            self._deliver(note)

    def _file(self, payload: bytes) -> Notification | None:
        """Files a response or chunk; returns a notification for the caller instead."""
        frame = cast("JsonValue", json.loads(payload))
        if not isinstance(frame, dict):
            raise ValueError("frame is not an object")
        if "method" in frame and "id" not in frame:
            note = Notification.from_json(frame)
            if note.method != "response.chunk":
                return note
            self._on_chunk(ResponseChunkParams.from_json(note.params))
        elif "method" not in frame and "id" in frame:
            self._on_response_frame(RpcResponse.from_json(frame))
        else:
            raise ValueError("frame is neither a notification nor a response")
        return None

    def _on_response_frame(self, response: RpcResponse) -> None:
        if response.id is None:
            error = response.error
            raise IpcProtocolFault(
                _PARSE_ERROR if error is None else error.code,
                "the add-in could not read a request" if error is None else error.message,
            )
        call = self._pending.get(response.id)
        if call is not None:  # otherwise the call timed out: discard
            call.response = response

    def _deliver(self, note: Notification) -> None:
        if self._on_notification is not None:
            self._on_notification(note.method, note.params)

    def _on_chunk(self, chunk: ResponseChunkParams) -> None:
        if chunk.id not in self._pending:
            return  # no longer waited for
        try:
            partial = chunks.add_chunk(self._partial.get(chunk.id), chunk)
        except ValueError:
            self._partial.pop(chunk.id, None)
            raise
        if not chunks.is_complete(partial):
            self._partial[chunk.id] = partial
            return
        self._partial.pop(chunk.id, None)
        response = RpcResponse.from_json(cast("JsonValue", json.loads(chunks.joined(partial))))
        if response.id != chunk.id:
            raise ValueError("response.chunk: joined frame answers another request")
        self._on_response_frame(response)

    # --- results ------------------------------------------------------------------------

    @staticmethod
    def _result_of(response: RpcResponse) -> JsonValue:
        error = response.error
        if error is None:
            return response.result
        if error.code == _CATALOGUE_ERROR and error.data is not None:
            raise IpcError.from_error(error.data)
        raise IpcProtocolFault(error.code, error.message)

    @staticmethod
    def _parse[T](read: Callable[[JsonValue], T], value: JsonValue) -> T:
        try:
            return read(value)
        except ValueError as exc:
            raise IpcProtocolFault(INVALID_RESPONSE, f"unusable result: {exc}") from None
