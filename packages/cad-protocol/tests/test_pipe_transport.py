"""Tests for NamedPipeTransport over Windows named pipe."""

import sys
import threading
import time

import pytest
from cad_protocol.client.pipe_transport import NamedPipeTransport
from cad_protocol.client.transport import TransportClosed, TransportTimeout
from cad_protocol.framing import encode_frame

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows named pipes only")

if sys.platform == "win32":
    import _winapi  # type: ignore[import-not-found]
else:
    _winapi = None


def test_named_pipe_send_and_receive() -> None:
    assert _winapi is not None
    pipe_name = rf"test-pipe-transport-{int(time.time() * 1000)}"
    full_path = rf"\\.\pipe\{pipe_name}"

    server_handle = _winapi.CreateNamedPipe(
        full_path,
        _winapi.PIPE_ACCESS_DUPLEX,
        0,
        1,
        65536,
        65536,
        0,
        0,
    )

    def server_worker() -> None:
        _winapi.ConnectNamedPipe(server_handle, False)
        # Read request frame
        header, _ = _winapi.ReadFile(server_handle, 4)
        length = int.from_bytes(header, "little")
        body, _ = _winapi.ReadFile(server_handle, length)
        assert body == b"ping"

        # Reply with frame
        reply = encode_frame(b"pong")
        _winapi.WriteFile(server_handle, reply)
        time.sleep(0.05)
        _winapi.CloseHandle(server_handle)

    server_thread = threading.Thread(target=server_worker)
    server_thread.start()

    transport = NamedPipeTransport(pipe_name)
    try:
        transport.send(b"ping")
        received = transport.receive(timeout_s=2.0)
        assert received == b"pong"
    finally:
        transport.close()
        server_thread.join()


def test_named_pipe_receive_timeout() -> None:
    assert _winapi is not None
    pipe_name = rf"test-pipe-timeout-{int(time.time() * 1000)}"
    full_path = rf"\\.\pipe\{pipe_name}"

    server_handle = _winapi.CreateNamedPipe(
        full_path,
        _winapi.PIPE_ACCESS_DUPLEX,
        0,
        1,
        65536,
        65536,
        0,
        0,
    )

    def server_worker() -> None:
        _winapi.ConnectNamedPipe(server_handle, False)
        time.sleep(0.3)
        _winapi.CloseHandle(server_handle)

    server_thread = threading.Thread(target=server_worker)
    server_thread.start()

    transport = NamedPipeTransport(pipe_name)
    try:
        with pytest.raises(TransportTimeout):
            transport.receive(timeout_s=0.1)
    finally:
        transport.close()
        server_thread.join()


def test_named_pipe_peer_closed() -> None:
    assert _winapi is not None
    pipe_name = rf"test-pipe-close-{int(time.time() * 1000)}"
    full_path = rf"\\.\pipe\{pipe_name}"

    server_handle = _winapi.CreateNamedPipe(
        full_path,
        _winapi.PIPE_ACCESS_DUPLEX,
        0,
        1,
        65536,
        65536,
        0,
        0,
    )

    def server_worker() -> None:
        _winapi.ConnectNamedPipe(server_handle, False)
        time.sleep(0.05)
        _winapi.CloseHandle(server_handle)

    server_thread = threading.Thread(target=server_worker)
    server_thread.start()

    transport = NamedPipeTransport(pipe_name)
    try:
        time.sleep(0.1)
        with pytest.raises(TransportClosed):
            transport.receive(timeout_s=0.5)
    finally:
        transport.close()
        server_thread.join()
