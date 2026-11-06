"""IpcClient behaviour over transcripts (spec 8.7): each test replays a scenario or builds one."""

import base64
import json
import traceback
from collections.abc import Callable
from typing import Any

import pytest
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import Meta, Operation, OperationGroup
from cad_protocol.backend import IpcBackend
from cad_protocol.client.ipc_client import IpcClient
from cad_protocol.errors import IpcError, IpcProtocolFault
from cad_protocol.replay import ReplayTransport, load_transcript

type Make = Callable[..., str]
type Text = Callable[[str], str]
type Events = list[tuple[str, JsonValue]]

TOKEN = "tok-5f2c91d7"
WRONG_TOKEN = "wrong-token-0000"
PARSE_ERROR = -32700
DWG = "C:/d/bracket.slddrw"
SHEET = "s_0123456789"
BACKEND: dict[str, Any] = {
    "protocol": "0.1",
    "addin_version": "0.1.0",
    "solidworks": {"version": "2025", "service_pack": "SP3.0", "ui_language": "en-US"},
    "capabilities": [],
    "operations": [],
    "licensed_modules": [],
    "warnings": [],
}


def _hello(request_id: int = 1, token: str = TOKEN) -> dict[str, Any]:
    params = {"token": token, "protocol": "0.1"}
    return {"jsonrpc": "2.0", "id": request_id, "method": "session.hello", "params": params}


def _ok(request_id: int, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _request(request_id: int, method: str, params: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def _chunk(request_id: int, index: int, count: int, data: bytes) -> dict[str, Any]:
    params = {
        "id": request_id,
        "index": index,
        "count": count,
        "data": base64.b64encode(data).decode("ascii"),
    }
    return {"jsonrpc": "2.0", "method": "response.chunk", "params": params}


def _relative(make: Make, entries: list[Any]) -> str:
    """A transcript from entries whose times are gaps since the previous entry."""
    total = 0
    absolute: list[Any] = []
    for direction, gap, frame in entries:
        total += gap
        absolute.append((direction, total, frame))
    return make(absolute)


def _prelude() -> list[Any]:
    return [("c2a", 0, _hello()), ("a2c", 20, _ok(1, BACKEND))]


def _snapshot_request(request_id: int) -> dict[str, Any]:
    return _request(request_id, "drawing.snapshot", {"document": DWG})


def _start(
    text: str, *, token: str = TOKEN, events: Events | None = None, **kwargs: Any
) -> tuple[IpcClient, ReplayTransport]:
    transport = ReplayTransport(load_transcript(text))
    sink = events if events is not None else []
    client = IpcClient(
        transport, token=token, on_notification=lambda m, p: sink.append((m, p)), **kwargs
    )
    return client, transport


def _is_code(info: pytest.ExceptionInfo[IpcError], code: str) -> bool:
    return info.value.code == code


def test_handshake(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("handshake"))
    hello = client.hello()
    assert hello.solidworks.version == "2025"
    assert hello.protocol == "0.1"
    assert client.ping().pong is True
    assert client.completed_operations() == ()
    assert transport.exhausted


def test_ids_count_from_one_and_meta_is_sent(make_transcript: Make) -> None:
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 100, _request(2, "session.ping", {})),
            ("a2c", 5, _ok(2, {"pong": True})),
            ("c2a", 100, _snapshot_request(3)),
            ("a2c", 5, _ok(3, {"k": "v"})),
        ],
    )
    client, transport = _start(text)
    client.hello()
    client.ping()
    client.snapshot_drawing(DWG, meta=Meta(request_id="r_9", job_id="j9"))
    ids = [frame["id"] for frame in transport.sent_frames]
    assert ids == [1, 2, 3]
    assert transport.sent_frames[2]["params"]["_meta"] == {"request_id": "r_9", "job_id": "j9"}
    assert transport.sent_frames[0]["params"] == {"token": TOKEN, "protocol": "0.1"}


def test_wrong_token_is_backend_lost(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("wrong_token"), token=WRONG_TOKEN)
    with pytest.raises(IpcError) as info:
        client.hello()
    assert _is_code(info, "BACKEND_LOST")
    assert info.value.retryable == "after_fix"
    assert transport.exhausted


def test_not_hello_first_is_backend_lost(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("not_hello_first"))
    with pytest.raises(IpcError) as info:
        client.ping()
    assert _is_code(info, "BACKEND_LOST")
    assert transport.exhausted


def test_token_not_in_error_text(fixture_text: Text) -> None:
    client, _ = _start(fixture_text("wrong_token"), token=WRONG_TOKEN)
    with pytest.raises(IpcError) as info:
        client.hello()
    rendered = [
        str(info.value),
        repr(info.value),
        info.value.message,
        json.dumps(info.value.details),
        "".join(traceback.format_exception(info.value)),
    ]
    assert all(WRONG_TOKEN not in text for text in rendered)


def test_major_mismatch_error(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("protocol_major_mismatch"), protocol="9.0")
    with pytest.raises(IpcError) as info:
        client.hello()
    assert _is_code(info, "BACKEND_VERSION_UNSUPPORTED")
    assert info.value.retryable == "never"
    with pytest.raises(IpcError) as after:  # the add-in closed the pipe
        client.ping()
    assert _is_code(after, "BACKEND_LOST")
    assert transport.exhausted


def test_solidworks_unsupported_leaves_the_pipe_open(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("solidworks_unsupported"))
    for _ in range(2):
        with pytest.raises(IpcError) as info:
            client.hello()
        assert _is_code(info, "BACKEND_VERSION_UNSUPPORTED")
    assert not transport.closed
    assert transport.exhausted


def test_returned_major_mismatch_closes(make_transcript: Make) -> None:
    text = _relative(
        make_transcript, [("c2a", 0, _hello()), ("a2c", 5, _ok(1, {**BACKEND, "protocol": "9.0"}))]
    )
    client, transport = _start(text)
    with pytest.raises(IpcError) as info:
        client.hello()
    assert _is_code(info, "BACKEND_VERSION_UNSUPPORTED")
    assert transport.closed


def test_snapshot_delivers_notifications_in_order(fixture_text: Text) -> None:
    events: Events = []
    client, transport = _start(fixture_text("snapshot_ok"), events=events)
    client.hello()
    result = client.snapshot_drawing(DWG, ["Sheet1"])
    assert [method for method, _ in events] == ["job.progress", "document.event"]
    assert events[0][1] == {"message": "Sheet1", "done": 0, "total": 1}
    assert isinstance(result, dict)
    assert result["drawing"] == {"document": "bracket_dwg", "revision": 3}
    assert transport.sent_frames[1]["params"] == {"document": DWG, "sheets": ["Sheet1"]}


def test_notifications_are_optional(fixture_text: Text) -> None:
    transport = ReplayTransport(load_transcript(fixture_text("snapshot_ok")))
    client = IpcClient(transport, token=TOKEN)
    client.hello()
    assert client.snapshot_drawing(DWG, ["Sheet1"]) is not None
    assert transport.exhausted


def test_chunks_joined(fixture_text: Text) -> None:
    events: Events = []
    client, transport = _start(fixture_text("snapshot_chunked"), events=events)
    client.hello()
    result = client.snapshot_drawing(DWG)
    assert isinstance(result, dict)
    sheets = result["sheets"]
    assert isinstance(sheets, dict)
    assert "图纸1" in json.dumps(result, ensure_ascii=False)
    assert sorted(sheets) == [SHEET, "s_0123456790"]
    assert [method for method, _ in events] == ["job.progress"]  # chunks are not events
    assert transport.exhausted


def test_chunks_split_inside_a_character(make_transcript: Make) -> None:
    frame = json.dumps(_ok(2, {"note": "草图"}), ensure_ascii=False).encode()
    cut = frame.index("草".encode()) + 1  # one byte into a three-byte character
    with pytest.raises(UnicodeDecodeError):
        frame[:cut].decode("utf-8")
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 10, _snapshot_request(2)),
            ("a2c", 5, _chunk(2, 0, 2, frame[:cut])),
            ("a2c", 1, _chunk(2, 1, 2, frame[cut:])),
        ],
    )
    client, _ = _start(text)
    client.hello()
    assert client.snapshot_drawing(DWG) == {"note": "草图"}


def test_late_chunks_are_discarded(make_transcript: Make) -> None:
    late = json.dumps(_ok(2, {"late": True})).encode()
    half = len(late) // 2
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 1000, _snapshot_request(2)),
            ("c2a", 121000, _request(3, "session.ping", {})),
            ("a2c", 10000, _chunk(2, 0, 2, late[:half])),
            ("a2c", 1, _chunk(2, 1, 2, late[half:])),
            ("a2c", 1, _ok(3, {"pong": True})),
        ],
    )
    client, transport = _start(text)
    client.hello()
    with pytest.raises(IpcError) as info:
        client.snapshot_drawing(DWG)
    assert _is_code(info, "EXEC_TIMEOUT")
    assert client.ping().pong is True  # the next call is not confused by the late chunks
    assert transport.exhausted


_BAD_CHUNKS: list[Any] = [
    pytest.param([_chunk(2, 1, 2, b"x")], id="starts-at-index-1"),
    pytest.param([_chunk(2, 0, 0, b"x")], id="zero-count"),
    pytest.param([_chunk(2, 0, 3, b"x"), _chunk(2, 2, 3, b"x")], id="skips-an-index"),
    pytest.param([_chunk(2, 0, 3, b"x"), _chunk(2, 1, 2, b"x")], id="count-changes"),
    pytest.param(
        [
            {
                "jsonrpc": "2.0",
                "method": "response.chunk",
                "params": {"id": 2, "index": 0, "count": 1, "data": "***"},
            }
        ],
        id="not-base64",
    ),
    pytest.param([_chunk(2, 0, 1, b'{"jsonrpc":"2.0","id":7,"result":{}}')], id="wrong-id"),
    pytest.param([_chunk(2, 0, 1, b'{"jsonrpc":"2.0","method":"x"}')], id="not-a-response"),
]


@pytest.mark.parametrize("chunks", _BAD_CHUNKS)
def test_chunk_out_of_order_or_bad_count_is_protocol_fault(
    make_transcript: Make, chunks: list[dict[str, Any]]
) -> None:
    entries = [*_prelude(), ("c2a", 10, _snapshot_request(2))]
    entries += [("a2c", 5, chunk) for chunk in chunks]
    client, _ = _start(_relative(make_transcript, entries))
    client.hello()
    with pytest.raises(IpcProtocolFault):
        client.snapshot_drawing(DWG)


def test_cancel_running(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("cancel_running"))
    client.hello()
    running = client.begin_snapshot_drawing(DWG)
    queued = client.begin_snapshot_drawing(DWG)
    assert client.cancel() is True  # waits for the running command's answer first
    for pending in (queued, running):
        with pytest.raises(IpcError) as info:
            pending.wait()
        assert _is_code(info, "EXEC_CANCELLED")
        assert info.value.retryable == "never"
    assert transport.exhausted


_LATE_BAD_CHUNKS: list[Any] = [
    pytest.param(_chunk(2, 1, 2, b"x"), id="bad-index"),
    pytest.param(
        {
            "jsonrpc": "2.0",
            "method": "response.chunk",
            "params": {"id": 2, "index": 0, "count": 1, "data": "***"},
        },
        id="bad-base64",
    ),
]


@pytest.mark.parametrize("late", _LATE_BAD_CHUNKS)
def test_late_malformed_chunk_is_discarded(make_transcript: Make, late: dict[str, Any]) -> None:
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 1000, _snapshot_request(2)),
            ("c2a", 121000, _request(3, "session.ping", {})),
            ("a2c", 10000, late),
            ("a2c", 1, _ok(3, {"pong": True})),
        ],
    )
    client, transport = _start(text)
    client.hello()
    with pytest.raises(IpcError) as info:
        client.snapshot_drawing(DWG)
    assert _is_code(info, "EXEC_TIMEOUT")
    assert client.ping().pong is True
    assert transport.exhausted


def test_protocol_code_with_data_is_a_protocol_fault(make_transcript: Make) -> None:
    data = {"code": "SOMETHING", "message": "m", "retryable": "safe"}
    reply = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32601, "message": "m", "data": data}}
    text = _relative(
        make_transcript, [*_prelude(), ("c2a", 10, _snapshot_request(2)), ("a2c", 5, reply)]
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcProtocolFault) as info:
        client.snapshot_drawing(DWG)
    assert info.value.rpc_code == -32601  # noqa: PLR2004


def test_cancel_waits_with_the_command_limit(make_transcript: Make) -> None:
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 10, _request(2, "job.cancel", {})),
            ("a2c", 60000, _ok(2, {"cancelled": True})),
        ],
    )
    client, transport = _start(text, read_timeout_s=30.0, command_timeout_s=120.0)
    client.hello()
    assert client.cancel() is True
    assert transport.exhausted


def test_notification_callback_error_is_not_a_protocol_fault(make_transcript: Make) -> None:
    note = {"jsonrpc": "2.0", "method": "job.progress", "params": {"message": "m"}}
    text = _relative(
        make_transcript,
        [*_prelude(), ("c2a", 10, _snapshot_request(2)), ("a2c", 5, note)],
    )

    def boom(method: str, params: JsonValue) -> None:
        raise ValueError("callback failed")

    transport = ReplayTransport(load_transcript(text))
    client = IpcClient(transport, token=TOKEN, on_notification=boom)
    client.hello()
    with pytest.raises(ValueError, match="callback failed") as info:
        client.snapshot_drawing(DWG)
    assert not isinstance(info.value, IpcProtocolFault)


class _ProgressTransport:
    """Answers every wait with a progress notification after 40 s on a fake clock."""

    def __init__(self, clock: list[float]) -> None:
        self.clock = clock
        self.waits: list[tuple[float, float]] = []  # (timeout asked, time left in the call)
        self.sent_at = 0.0

    def send(self, payload: bytes) -> None:
        del payload
        self.sent_at = self.clock[0]

    def receive(self, timeout_s: float) -> bytes:
        self.waits.append((timeout_s, 100.0 - (self.clock[0] - self.sent_at)))
        self.clock[0] += 40.0
        note = {"jsonrpc": "2.0", "method": "job.progress", "params": {"message": "m"}}
        return json.dumps(note).encode()

    def close(self) -> None:
        return None


def test_time_limit_covers_the_whole_call() -> None:
    clock = [1000.0]
    transport = _ProgressTransport(clock)
    client = IpcClient(transport, token=TOKEN, command_timeout_s=100.0, monotonic=lambda: clock[0])
    with pytest.raises(IpcError) as info:
        client.snapshot_drawing(DWG)
    assert _is_code(info, "EXEC_TIMEOUT")
    assert transport.waits
    assert all(asked <= left + 1e-9 for asked, left in transport.waits)
    assert len(transport.waits) == 3  # noqa: PLR2004 - 100, 60, 20 s; then nothing remains


def _open(operation_id: str, path: str) -> Operation:
    return Operation(
        operation_id=operation_id,
        op="document.open",
        params={"path": path, "read_only": False, "fully_resolved": True},
    )


def test_duplicate_carries_original_result(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("ops_duplicate"))
    client.hello()
    first = client.apply_ops(
        [
            OperationGroup(document="C:/d/a.sldprt", operations=(_open("j1:1", "C:/d/a.sldprt"),)),
            OperationGroup(document="C:/d/b.sldprt", operations=(_open("j1:2", "C:/d/b.sldprt"),)),
        ]
    )
    assert [o.operation_id for o in first.outcomes] == ["j1:1", "j1:2"]
    assert all(o.error is None for o in first.outcomes)
    second = client.apply_ops(
        [
            OperationGroup(
                document="C:/d/b.sldprt",
                operations=(_open("j1:2", "C:/d/b.sldprt"), _open("j1:3", "C:/d/a.sldprt")),
            )
        ]
    )
    assert len(second.outcomes) == 1  # the batch stopped at the duplicate
    outcome = second.outcomes[0]
    assert outcome.error is not None
    assert outcome.error.code == "DUPLICATE_OPERATION"
    assert outcome.result == {"owned": False}
    error = IpcError.from_outcome(outcome)
    assert error.code == "DUPLICATE_OPERATION"
    assert error.original_result == {"owned": False}
    assert client.completed_operations() == ("j1:1", "j1:2")
    assert transport.exhausted


def test_failure_stops_batch(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("ops_failure_stops"))
    client.hello()
    group = OperationGroup(
        document="C:/d/a.sldprt",
        operations=(
            _open("j2:1", "C:/d/a.sldprt"),
            _open("j2:2", "D:/x/c.sldprt"),
            Operation(operation_id="j2:3", op="document.close", params={"path": "C:/d/a.sldprt"}),
        ),
    )
    result = client.apply_ops([group])
    assert [o.operation_id for o in result.outcomes] == ["j2:1", "j2:2"]
    assert result.outcomes[1].error is not None
    assert result.outcomes[1].error.code == "AUTH_PATH_DENIED"
    assert client.completed_operations() == ("j2:1",)
    assert IpcError.from_outcome(result.outcomes[1]).original_result is None
    assert transport.exhausted


def test_timeout_no_resend_then_late_response_discarded(fixture_text: Text) -> None:
    # Any resend of the snapshot would not match the next expected frame
    # (completed_operations), and the replay would raise TranscriptMismatch.
    client, transport = _start(fixture_text("timeout_late_response"))
    client.hello()
    with pytest.raises(IpcError) as info:
        client.snapshot_drawing(DWG)
    assert _is_code(info, "EXEC_TIMEOUT")
    assert info.value.retryable == "after_fix"
    assert client.completed_operations() == ()  # the late result for id 2 was skipped
    methods = [frame["method"] for frame in transport.sent_frames]
    assert methods == ["session.hello", "drawing.snapshot", "session.completed_operations"]
    assert transport.exhausted


def test_backend_lost(fixture_text: Text) -> None:
    client, transport = _start(fixture_text("backend_lost"))
    client.hello()
    with pytest.raises(IpcError) as info:
        client.snapshot_drawing(DWG)
    assert _is_code(info, "BACKEND_LOST")
    sent = len(transport.sent_frames)
    with pytest.raises(IpcError) as after:
        client.ping()
    assert _is_code(after, "BACKEND_LOST")
    assert len(transport.sent_frames) == sent  # nothing more was written


def test_backend_lost_fails_every_waiting_call(make_transcript: Make) -> None:
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 10, _snapshot_request(2)),
            ("c2a", 1, _snapshot_request(3)),
            ("close", 5, None),
        ],
    )
    client, _ = _start(text)
    client.hello()
    first = client.begin_snapshot_drawing(DWG)
    second = client.begin_snapshot_drawing(DWG)
    for pending in (first, second):
        with pytest.raises(IpcError) as info:
            pending.wait()
        assert _is_code(info, "BACKEND_LOST")


def test_unknown_error_code_kept_as_text(make_transcript: Make) -> None:
    data = {"code": "SOMETHING_NEW", "message": "from a newer add-in", "retryable": "safe"}
    reply = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32000, "message": "m", "data": data}}
    text = _relative(
        make_transcript,
        [*_prelude(), ("c2a", 10, _snapshot_request(2)), ("a2c", 5, reply)],
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcError) as info:
        client.snapshot_drawing(DWG)
    assert info.value.code == "SOMETHING_NEW"
    assert info.value.retryable == "safe"
    assert info.value.message == "from a newer add-in"


@pytest.mark.parametrize("rpc_code", [-32700, -32600, -32601, -32602, -32603])
def test_protocol_fault_raised(make_transcript: Make, rpc_code: int) -> None:
    reply = {"jsonrpc": "2.0", "id": 2, "error": {"code": rpc_code, "message": "bad"}}
    text = _relative(
        make_transcript, [*_prelude(), ("c2a", 10, _snapshot_request(2)), ("a2c", 5, reply)]
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcProtocolFault) as info:
        client.snapshot_drawing(DWG)
    assert info.value.rpc_code == rpc_code
    assert info.value.message == "bad"


def test_catalogue_error_without_data_is_protocol_fault(make_transcript: Make) -> None:
    reply = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32000, "message": "no data"}}
    text = _relative(
        make_transcript, [*_prelude(), ("c2a", 10, _snapshot_request(2)), ("a2c", 5, reply)]
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcProtocolFault):
        client.snapshot_drawing(DWG)


def test_ui_blocked_notification_delivered(fixture_text: Text) -> None:
    events: Events = []
    client, transport = _start(fixture_text("ui_blocked"), events=events)
    client.hello()
    result = client.snapshot_drawing(DWG)  # the client does not fail the job itself
    assert events == [("session.ui_blocked", {"waited_ms": 30000})]
    assert isinstance(result, dict)
    assert transport.exhausted


def test_malformed_result_is_protocol_fault(make_transcript: Make) -> None:
    text = _relative(
        make_transcript,
        [*_prelude(), ("c2a", 10, _request(2, "session.ping", {})), ("a2c", 5, _ok(2, {}))],
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcProtocolFault, match="pong"):
        client.ping()


def test_missing_result_is_protocol_fault(make_transcript: Make) -> None:
    reply = {"jsonrpc": "2.0", "id": 2}
    text = _relative(
        make_transcript,
        [*_prelude(), ("c2a", 10, _request(2, "session.ping", {})), ("a2c", 5, reply)],
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcProtocolFault):
        client.ping()


def test_result_may_be_null_for_a_snapshot(make_transcript: Make) -> None:
    text = _relative(
        make_transcript, [*_prelude(), ("c2a", 10, _snapshot_request(2)), ("a2c", 5, _ok(2, None))]
    )
    client, _ = _start(text)
    client.hello()
    assert client.snapshot_drawing(DWG) is None


def test_malformed_frame_is_protocol_fault() -> None:
    class Garbage:
        def send(self, payload: bytes) -> None:
            del payload

        def receive(self, timeout_s: float) -> bytes:
            del timeout_s
            return b"not json"

        def close(self) -> None:
            return None

    client = IpcClient(Garbage(), token=TOKEN)
    with pytest.raises(IpcProtocolFault):
        client.ping()


def test_unexpected_frame_shape_is_protocol_fault(make_transcript: Make) -> None:
    odd: dict[str, Any] = {"jsonrpc": "2.0", "id": 9, "method": "server.request", "params": {}}
    text = _relative(
        make_transcript,
        [*_prelude(), ("c2a", 10, _request(2, "session.ping", {})), ("a2c", 5, odd)],
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcProtocolFault):
        client.ping()


def test_response_with_null_id_is_protocol_fault(make_transcript: Make) -> None:
    reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
    text = _relative(
        make_transcript,
        [*_prelude(), ("c2a", 10, _request(2, "session.ping", {})), ("a2c", 5, reply)],
    )
    client, _ = _start(text)
    client.hello()
    with pytest.raises(IpcProtocolFault) as info:
        client.ping()
    assert info.value.rpc_code == PARSE_ERROR


def test_calls_after_close_are_backend_lost(make_transcript: Make) -> None:
    client, transport = _start(_relative(make_transcript, _prelude()))
    client.hello()
    client.close()
    client.close()  # idempotent
    assert transport.closed
    with pytest.raises(IpcError) as info:
        client.ping()
    assert _is_code(info, "BACKEND_LOST")


def test_unsolicited_response_is_discarded(make_transcript: Make) -> None:
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 10, _request(2, "session.ping", {})),
            ("a2c", 1, _ok(77, {"pong": True})),
            ("a2c", 1, _ok(2, {"pong": True})),
        ],
    )
    client, transport = _start(text)
    client.hello()
    assert client.ping().pong is True
    assert transport.exhausted


def test_backend_wraps_the_client(fixture_text: Text) -> None:
    client, _ = _start(fixture_text("ops_failure_stops"))
    backend = IpcBackend(client)  # performs the handshake
    assert backend.session.solidworks.service_pack == "SP3.0"
    group = OperationGroup(
        document="C:/d/a.sldprt",
        operations=(
            _open("j2:1", "C:/d/a.sldprt"),
            _open("j2:2", "D:/x/c.sldprt"),
            Operation(operation_id="j2:3", op="document.close", params={"path": "C:/d/a.sldprt"}),
        ),
    )
    assert len(backend.apply_ops([group]).outcomes) == 2  # noqa: PLR2004
    assert backend.completed_operations() == ("j2:1",)
    backend.close()


def test_backend_snapshot_and_cancel(make_transcript: Make) -> None:
    text = _relative(
        make_transcript,
        [
            *_prelude(),
            ("c2a", 10, _snapshot_request(2)),
            ("a2c", 5, _ok(2, {"k": 1})),
            ("c2a", 10, _request(3, "job.cancel", {})),
            ("a2c", 5, _ok(3, {"cancelled": False})),
        ],
    )
    client, _ = _start(text)
    backend = IpcBackend(client)
    assert backend.snapshot_drawing(DWG) == {"k": 1}
    assert backend.cancel() is False
