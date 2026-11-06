"""Length-prefixed framing (ADR-036): 4-byte little-endian length, then the payload."""

import io
from typing import Any, BinaryIO, cast

import pytest
from cad_protocol.errors import FrameError
from cad_protocol.framing import MAX_FRAME_BYTES, encode_frame, read_frame

HEADER_BYTES = 4


class _OneByteReads(io.RawIOBase):
    """A stream that returns at most one byte per ``read``, as a pipe may."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        if self._pos >= len(self._data):
            return 0
        buffer[0] = self._data[self._pos]
        self._pos += 1
        return 1


def test_golden_bytes() -> None:
    assert encode_frame(b'{"id":1}') == bytes.fromhex("08000000") + b'{"id":1}'


def test_default_limit_is_64_mib() -> None:
    assert MAX_FRAME_BYTES == 64 * 1024 * 1024


def test_round_trip() -> None:
    first = '{"name":"草图"}'.encode()
    second = b"{}"
    stream = io.BytesIO(encode_frame(first) + encode_frame(second))
    assert read_frame(stream) == first
    assert read_frame(stream) == second
    assert read_frame(stream) is None


def test_empty_payload_round_trips() -> None:
    assert read_frame(io.BytesIO(encode_frame(b""))) == b""


@pytest.mark.parametrize(
    "data",
    [b"\x05\x00", b"\x05\x00\x00\x00abc"],
    ids=["header", "body"],
)
def test_truncated_header_and_body(data: bytes) -> None:
    with pytest.raises(FrameError, match="truncated"):
        read_frame(io.BytesIO(data))


def test_length_over_limit_rejected_before_reading() -> None:
    stream = io.BytesIO((100).to_bytes(4, "little") + b"x" * 100)
    with pytest.raises(FrameError, match="limit"):
        read_frame(stream, max_bytes=10)
    assert stream.tell() == HEADER_BYTES  # only the header was consumed


def test_encode_over_limit_rejected() -> None:
    with pytest.raises(FrameError, match="limit"):
        encode_frame(b"x" * 11, max_bytes=10)
    assert encode_frame(b"x" * 10, max_bytes=10)[4:] == b"x" * 10


def test_clean_end_returns_none() -> None:
    assert read_frame(io.BytesIO(b"")) is None


def test_short_reads_are_joined() -> None:
    stream = cast("BinaryIO", _OneByteReads(encode_frame(b"abcdef")))
    assert read_frame(stream) == b"abcdef"
    assert read_frame(stream) is None
