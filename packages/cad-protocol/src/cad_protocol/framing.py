"""Length-prefixed frames (ADR-036): a 4-byte little-endian length, then the payload."""

from typing import BinaryIO

from cad_protocol.errors import FrameError

MAX_FRAME_BYTES = 64 * 1024 * 1024
_HEADER_BYTES = 4


def encode_frame(payload: bytes, max_bytes: int = MAX_FRAME_BYTES) -> bytes:
    if len(payload) > max_bytes:
        raise FrameError(f"frame of {len(payload)} bytes is over the {max_bytes}-byte limit")
    return len(payload).to_bytes(_HEADER_BYTES, "little") + payload


def _read_exactly(stream: BinaryIO, count: int) -> bytes:
    """Up to ``count`` bytes; fewer only at the end of the stream (reads may come back short)."""
    chunks: list[bytes] = []
    remaining = count
    while remaining > 0:
        piece = stream.read(remaining)
        if not piece:
            break
        chunks.append(piece)
        remaining -= len(piece)
    return b"".join(chunks)


def read_frame(stream: BinaryIO, max_bytes: int = MAX_FRAME_BYTES) -> bytes | None:
    """The next payload, or ``None`` at a clean end of stream."""
    header = _read_exactly(stream, _HEADER_BYTES)
    if not header:
        return None
    if len(header) < _HEADER_BYTES:
        raise FrameError("truncated frame header")
    length = int.from_bytes(header, "little")
    if length > max_bytes:
        raise FrameError(f"frame of {length} bytes is over the {max_bytes}-byte limit")
    body = _read_exactly(stream, length)
    if len(body) < length:
        raise FrameError("truncated frame body")
    return body
