"""Windows named pipe transport using length-prefixed framing (ADR-036, spec 8.6.1)."""

import contextlib
import sys
import time
from typing import Final

from cad_protocol.client.transport import Transport, TransportClosed, TransportTimeout
from cad_protocol.errors import FrameError
from cad_protocol.framing import MAX_FRAME_BYTES, encode_frame

_HEADER_BYTES: Final = 4
_POLL_INTERVAL_S: Final = 0.01
_ERROR_PIPE_BUSY: Final = 231

if sys.platform == "win32":
    import _winapi  # type: ignore[import-not-found]
else:
    _winapi = None


class NamedPipeTransport(Transport):
    """Duplex transport over a Windows named pipe with 4-byte little-endian framing."""

    def __init__(self, pipe_name: str, *, connect_timeout_s: float = 5.0) -> None:
        if sys.platform != "win32" or _winapi is None:
            raise NotImplementedError("NamedPipeTransport is only supported on Windows.")

        self._pipe_path = pipe_name if pipe_name.startswith(r"\\") else rf"\\.\pipe\{pipe_name}"
        self._closed = False
        self._handle = self._connect(self._pipe_path, connect_timeout_s)

    @classmethod
    def from_handle(cls, handle: int) -> "NamedPipeTransport":
        """Wrap an existing connected pipe handle."""
        inst = cls.__new__(cls)
        inst._pipe_path = "<handle>"
        inst._closed = False
        inst._handle = handle
        return inst

    @staticmethod
    def _connect(path: str, timeout_s: float) -> int:
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                handle = _winapi.CreateFile(  # type: ignore[attr-defined]
                    path,
                    _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,  # type: ignore[attr-defined]
                    0,
                    0,
                    _winapi.OPEN_EXISTING,  # type: ignore[attr-defined]
                    0,
                    0,
                )
                return int(handle)
            except OSError as exc:
                err = getattr(exc, "winerror", None)
                if err == _ERROR_PIPE_BUSY:  # Pipe busy, wait for it
                    remaining_ms = int(max(0.05, deadline - time.monotonic()) * 1000)
                    with contextlib.suppress(OSError):
                        _winapi.WaitNamedPipe(path, remaining_ms)  # type: ignore[attr-defined]
                if time.monotonic() >= deadline:
                    raise TransportClosed(f"Could not connect to named pipe {path}: {exc}") from exc
                time.sleep(0.05)

    def send(self, payload: bytes) -> None:
        if self._closed or _winapi is None:
            raise TransportClosed("Transport is closed.")
        frame = encode_frame(payload)
        try:
            _winapi.WriteFile(self._handle, frame)  # type: ignore[attr-defined]
        except OSError as exc:
            self.close()
            raise TransportClosed(f"Pipe write failed: {exc}") from exc

    def receive(self, timeout_s: float) -> bytes:
        if self._closed or _winapi is None:
            raise TransportClosed("Transport is closed.")

        header = self._read_exact(_HEADER_BYTES, timeout_s)
        length = int.from_bytes(header, "little")
        if length > MAX_FRAME_BYTES:
            raise FrameError(f"Frame length {length} exceeds maximum {MAX_FRAME_BYTES}")
        return self._read_exact(length, timeout_s)

    def _read_exact(self, count: int, timeout_s: float) -> bytes:
        assert _winapi is not None
        deadline = time.monotonic() + timeout_s
        buffer = bytearray()
        while len(buffer) < count:
            if self._closed:
                raise TransportClosed("Transport is closed.")
            try:
                avail, _ = _winapi.PeekNamedPipe(self._handle, 0)  # type: ignore[attr-defined]
            except OSError as exc:
                self.close()
                raise TransportClosed(f"Pipe peek failed: {exc}") from exc

            avail_bytes = avail if isinstance(avail, int) else len(avail)
            if avail_bytes > 0:
                needed = count - len(buffer)
                to_read = min(avail_bytes, needed)
                try:
                    chunk, _ = _winapi.ReadFile(self._handle, to_read)  # type: ignore[attr-defined]
                except OSError as exc:
                    self.close()
                    raise TransportClosed(f"Pipe read failed: {exc}") from exc
                if not chunk:
                    self.close()
                    raise TransportClosed("Pipe reached end of stream.")
                buffer.extend(chunk)
            else:
                if time.monotonic() >= deadline:
                    raise TransportTimeout("Timed out waiting for frame.")
                time.sleep(_POLL_INTERVAL_S)

        return bytes(buffer)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if _winapi is not None and self._handle:
                with contextlib.suppress(OSError):
                    _winapi.CloseHandle(self._handle)  # type: ignore[attr-defined]
