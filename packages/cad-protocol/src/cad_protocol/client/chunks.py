"""Joining ``response.chunk`` notifications (spec 8.7): chunks split bytes, not text."""

import base64

from cad_ir.generated.ipc import ResponseChunkParams

type Partial = tuple[int, tuple[bytes, ...]]  # (count, pieces so far)


def add_chunk(partial: Partial | None, chunk: ResponseChunkParams) -> Partial:
    """The state after ``chunk``. Raises ``ValueError`` on a bad count, order or encoding."""
    if chunk.count < 1:
        raise ValueError("response.chunk: count must be at least 1")
    count, pieces = (chunk.count, ()) if partial is None else partial
    if chunk.count != count:
        raise ValueError("response.chunk: count changed between chunks")
    if chunk.index != len(pieces):
        raise ValueError(f"response.chunk: expected index {len(pieces)}, got {chunk.index}")
    piece = base64.b64decode(chunk.data, validate=True)
    return count, (*pieces, piece)


def is_complete(partial: Partial) -> bool:
    return len(partial[1]) == partial[0]


def joined(partial: Partial) -> bytes:
    return b"".join(partial[1])
