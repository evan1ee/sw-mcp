"""The transcript loader and ReplayTransport: masking, timing and mismatch reporting."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from cad_protocol.client.transport import TransportClosed, TransportTimeout
from cad_protocol.replay import ReplayTransport, TranscriptMismatch, load_transcript

type Make = Callable[..., str]


def _bytes(frame: dict[str, Any]) -> bytes:
    return json.dumps(frame).encode()


def _ping(request_id: int, **extra: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "method": "session.ping", "params": extra}


def _pong(request_id: int) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"pong": True}}


def test_load_transcript_reads_header_and_entries(make_transcript: Make) -> None:
    transcript = load_transcript(
        make_transcript([("c2a", 0, _ping(1)), ("a2c", 5, _pong(1)), ("close", 9, None)])
    )
    assert transcript.header.scenario == "inline"
    assert transcript.header.sides == ("python",)
    assert transcript.header.config["token"] == "tok-5f2c91d7"
    assert [(e.direction, e.t_ms, e.is_close) for e in transcript.entries] == [
        ("core_to_addin", 0, False),
        ("addin_to_core", 5, False),
        ("addin_to_core", 9, True),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json\n",
        '{"transcript":"9","scenario":"x","source":"synthetic","sides":["python"],"config":{}}\n',
        '{"transcript":"0.1","scenario":"x","source":"dreamed","sides":["python"],"config":{}}\n',
        '{"transcript":"0.1","scenario":"x","source":"synthetic","sides":["java"],"config":{}}\n',
        '{"transcript":"0.1","scenario":"x","source":"synthetic","sides":["python"]}\n',
    ],
    ids=["empty", "header-not-json", "version", "source", "side", "no-config"],
)
def test_load_transcript_rejects_bad_header(text: str) -> None:
    with pytest.raises(ValueError, match=r"transcript|header|line 1"):
        load_transcript(text)


@pytest.mark.parametrize(
    "entries",
    [
        [("c2a", 10, _ping(1)), ("a2c", 5, _pong(1))],
        [("c2a", 0, None)],
    ],
    ids=["time-goes-backwards", "no-frame"],
)
def test_load_transcript_rejects_bad_entries(make_transcript: Make, entries: list[object]) -> None:
    with pytest.raises(ValueError, match=r"line 2|line 3|t_ms|frame"):
        load_transcript(make_transcript(entries))


def test_mismatched_send_raises(make_transcript: Make) -> None:
    transport = ReplayTransport(load_transcript(make_transcript([("c2a", 0, _ping(1))])))
    other: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": "nope.nope", "params": {}}
    with pytest.raises(TranscriptMismatch) as info:
        transport.send(_bytes(other))
    assert "nope.nope" in str(info.value)  # what was sent
    assert "session.ping" in str(info.value)  # what was expected


def test_masks_meta(make_transcript: Make) -> None:
    meta_a = {"_meta": {"request_id": "a", "job_id": "j1"}}
    meta_b = {"_meta": {"request_id": "b"}}
    transport = ReplayTransport(
        load_transcript(make_transcript([("c2a", 0, _ping(1, **meta_a)), ("c2a", 1, _ping(2))]))
    )
    transport.send(_bytes(_ping(1, **meta_b)))  # different _meta: still matches
    with pytest.raises(TranscriptMismatch):
        transport.send(_bytes(_ping(3)))  # different id: does not


def test_mismatch_message_hides_token(make_transcript: Make) -> None:
    hello: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "session.hello",
        "params": {"token": "secret-one", "protocol": "0.1"},
    }
    transport = ReplayTransport(load_transcript(make_transcript([("c2a", 0, hello)])))
    sent: dict[str, Any] = {**hello, "params": {"token": "secret-two", "protocol": "0.1"}}
    with pytest.raises(TranscriptMismatch) as info:
        transport.send(_bytes(sent))
    assert "secret-one" not in str(info.value)
    assert "secret-two" not in str(info.value)


def test_timeout_from_t_ms(make_transcript: Make) -> None:
    transport = ReplayTransport(
        load_transcript(make_transcript([("c2a", 1000, _ping(1)), ("a2c", 4000, _pong(1))]))
    )
    transport.send(_bytes(_ping(1)))
    with pytest.raises(TransportTimeout):
        transport.receive(2.0)  # the frame is 3 s after the send
    with pytest.raises(TransportTimeout):
        transport.receive(2.9)  # and stays next in line
    assert json.loads(transport.receive(3.0)) == _pong(1)
    assert transport.exhausted


def test_receive_before_a_required_send_raises(make_transcript: Make) -> None:
    transport = ReplayTransport(
        load_transcript(make_transcript([("c2a", 0, _ping(1)), ("a2c", 5, _pong(1))]))
    )
    with pytest.raises(TranscriptMismatch):
        transport.receive(1.0)


def test_send_while_frames_are_pending_raises(make_transcript: Make) -> None:
    transport = ReplayTransport(
        load_transcript(make_transcript([("a2c", 0, _pong(1)), ("c2a", 5, _ping(2))]))
    )
    with pytest.raises(TranscriptMismatch):
        transport.send(_bytes(_ping(2)))


def test_close_entry_closes_both_directions(make_transcript: Make) -> None:
    transport = ReplayTransport(
        load_transcript(make_transcript([("c2a", 0, _ping(1)), ("close", 5, None)]))
    )
    transport.send(_bytes(_ping(1)))
    with pytest.raises(TransportClosed):
        transport.receive(1.0)
    with pytest.raises(TransportClosed):
        transport.send(_bytes(_ping(2)))
    assert transport.exhausted


def test_send_into_a_close_entry_is_closed(make_transcript: Make) -> None:
    transport = ReplayTransport(load_transcript(make_transcript([("close", 0, None)])))
    with pytest.raises(TransportClosed):
        transport.send(_bytes(_ping(1)))
    assert transport.exhausted


def test_close_marks_the_transport_closed(make_transcript: Make) -> None:
    transport = ReplayTransport(load_transcript(make_transcript([("c2a", 0, _ping(1))])))
    assert not transport.closed
    transport.close()
    assert transport.closed
    with pytest.raises(TransportClosed):
        transport.send(_bytes(_ping(1)))


def test_sent_frames_are_recorded(make_transcript: Make) -> None:
    transport = ReplayTransport(load_transcript(make_transcript([("c2a", 0, _ping(1))])))
    transport.send(_bytes(_ping(1, _meta={"request_id": "r"})))
    assert transport.sent_frames == (_ping(1, _meta={"request_id": "r"}),)
