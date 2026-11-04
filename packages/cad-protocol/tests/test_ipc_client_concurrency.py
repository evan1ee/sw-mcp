"""Tests for IpcClient concurrency, reader thread and heartbeat (spec 8.6.3, ADR-053)."""

import json
import queue
import threading
from typing import Any, cast

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import Meta
from cad_protocol.client.ipc_client import IpcClient
from cad_protocol.client.transport import Transport, TransportClosed, TransportTimeout
from cad_protocol.errors import IpcError

TOKEN = "tok-5f2c91d7"
BACKEND_INFO: dict[str, Any] = {
    "protocol": "0.1",
    "addin_version": "0.1.0",
    "solidworks": {"version": "2025", "service_pack": "SP3.0", "ui_language": "en-US"},
    "capabilities": ["drawing.snapshot"],
    "operations": [],
    "licensed_modules": [],
    "warnings": [],
}


class QueueTransport(Transport):
    """A thread-safe in-memory transport using queues."""

    def __init__(self) -> None:
        self.to_addin: queue.Queue[bytes] = queue.Queue()
        self.to_client: queue.Queue[bytes] = queue.Queue()
        self._closed = False
        self._lock = threading.Lock()

    def send(self, payload: bytes) -> None:
        with self._lock:
            if self._closed:
                raise TransportClosed
        self.to_addin.put(payload)

    def receive(self, timeout_s: float) -> bytes:
        with self._lock:
            if self._closed:
                raise TransportClosed
        try:
            return self.to_client.get(timeout=max(timeout_s, 0.001))
        except queue.Empty:
            with self._lock:
                if self._closed:
                    raise TransportClosed from None
            raise TransportTimeout from None

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self.to_client.put(b"")  # unblock any waiters

    def put_response(self, frame: dict[str, Any]) -> None:
        self.to_client.put(json.dumps(frame, ensure_ascii=False).encode("utf-8"))

    def get_sent_frame(self, timeout_s: float = 2.0) -> dict[str, Any]:
        raw = self.to_addin.get(timeout=timeout_s)
        return cast(dict[str, Any], json.loads(raw.decode("utf-8")))


def test_reader_thread_receives_responses() -> None:
    transport = QueueTransport()
    client = IpcClient(transport, token=TOKEN, reader_thread=True, heartbeat_interval_s=100.0)
    try:
        # Hello call
        def answer_hello() -> None:
            frame = transport.get_sent_frame()
            assert frame["method"] == "session.hello"
            transport.put_response({"jsonrpc": "2.0", "id": frame["id"], "result": BACKEND_INFO})

        worker = threading.Thread(target=answer_hello)
        worker.start()

        hello = client.hello()
        assert hello.solidworks.version == "2025"
        worker.join()
    finally:
        client.close()


def test_immediate_notification_delivery_while_command_pending() -> None:
    transport = QueueTransport()
    notifications: list[tuple[str, JsonValue]] = []
    delivered = threading.Event()

    def on_note(method: str, params: JsonValue) -> None:
        notifications.append((method, params))
        delivered.set()

    client = IpcClient(
        transport,
        token=TOKEN,
        on_notification=on_note,
        reader_thread=True,
        heartbeat_interval_s=100.0,
    )
    try:
        # Step 1: send hello
        def answer_hello() -> None:
            f = transport.get_sent_frame()
            transport.put_response({"jsonrpc": "2.0", "id": f["id"], "result": BACKEND_INFO})

        threading.Thread(target=answer_hello).start()
        client.hello()

        # Step 2: start drawing.snapshot in background
        snapshot_result: list[Any] = []
        snapshot_done = threading.Event()

        def do_snapshot() -> None:
            res = client.snapshot_drawing("C:\\a.slddrw")
            snapshot_result.append(res)
            snapshot_done.set()

        thread = threading.Thread(target=do_snapshot)
        thread.start()

        # Add-in receives drawing.snapshot request
        snap_req = transport.get_sent_frame()
        assert snap_req["method"] == "drawing.snapshot"

        # While snapshot is running, add-in pushes a notification
        transport.put_response(
            {"jsonrpc": "2.0", "method": "session.ui_blocked", "params": {"waited_ms": 1000}}
        )

        # The notification must be delivered immediately to the callback before snapshot returns!
        assert delivered.wait(timeout=2.0)
        assert len(notifications) == 1
        assert notifications[0][0] == "session.ui_blocked"
        assert not snapshot_done.is_set()

        # Now return snapshot result
        transport.put_response({"jsonrpc": "2.0", "id": snap_req["id"], "result": {"sheets": []}})
        assert snapshot_done.wait(timeout=2.0)
        assert snapshot_result == [{"sheets": []}]
        thread.join()
    finally:
        client.close()


def test_concurrent_cancel_while_command_pending() -> None:
    transport = QueueTransport()
    client = IpcClient(transport, token=TOKEN, reader_thread=True, heartbeat_interval_s=100.0)
    try:
        # Hello
        def answer_hello() -> None:
            f = transport.get_sent_frame()
            transport.put_response({"jsonrpc": "2.0", "id": f["id"], "result": BACKEND_INFO})

        threading.Thread(target=answer_hello).start()
        client.hello()

        # Worker thread begins command
        cmd_error: list[IpcError] = []

        def do_command() -> None:
            try:
                client.snapshot_drawing("C:\\part.slddrw", meta=Meta(job_id="job_1"))
            except IpcError as e:
                cmd_error.append(e)

        worker = threading.Thread(target=do_command)
        worker.start()

        # Add-in gets snapshot frame
        snap_frame = transport.get_sent_frame()
        assert snap_frame["method"] == "drawing.snapshot"

        # Second thread calls cancel() concurrently
        cancel_result: list[bool] = []
        cancel_done = threading.Event()

        def do_cancel() -> None:
            res = client.cancel(meta=Meta(job_id="job_1"))
            cancel_result.append(res)
            cancel_done.set()

        cancel_thread = threading.Thread(target=do_cancel)
        cancel_thread.start()

        # Add-in receives job.cancel frame
        cancel_frame = transport.get_sent_frame()
        assert cancel_frame["method"] == "job.cancel"

        # Add-in answers cancel first
        transport.put_response(
            {"jsonrpc": "2.0", "id": cancel_frame["id"], "result": {"cancelled": True}}
        )
        assert cancel_done.wait(timeout=2.0)
        assert cancel_result == [True]
        cancel_thread.join()

        # Add-in answers snapshot with EXEC_CANCELLED
        transport.put_response(
            {
                "jsonrpc": "2.0",
                "id": snap_frame["id"],
                "error": {
                    "code": -32000,
                    "message": "Cancelled",
                    "data": {
                        "code": "EXEC_CANCELLED",
                        "message": "The job was cancelled.",
                        "retryable": "after_fix",
                    },
                },
            }
        )
        worker.join()
        assert len(cmd_error) == 1
        assert cmd_error[0].code == "EXEC_CANCELLED"
    finally:
        client.close()


def test_pipe_disconnect_wakes_pending_command() -> None:
    transport = QueueTransport()
    client = IpcClient(transport, token=TOKEN, reader_thread=True, heartbeat_interval_s=100.0)
    try:

        def answer_hello() -> None:
            f = transport.get_sent_frame()
            transport.put_response({"jsonrpc": "2.0", "id": f["id"], "result": BACKEND_INFO})

        threading.Thread(target=answer_hello).start()
        client.hello()

        err: list[IpcError] = []
        done = threading.Event()

        def do_command() -> None:
            try:
                client.snapshot_drawing("C:\\a.slddrw")
            except IpcError as e:
                err.append(e)
            finally:
                done.set()

        worker = threading.Thread(target=do_command)
        worker.start()

        # Add-in gets snapshot frame
        transport.get_sent_frame()

        # Transport abruptly closes
        transport.close()

        # The command must immediately wake up and raise BACKEND_LOST
        assert done.wait(timeout=2.0)
        assert len(err) == 1
        assert err[0].code == "BACKEND_LOST"
        worker.join()
    finally:
        client.close()


def test_heartbeat_sends_ping_when_idle() -> None:
    transport = QueueTransport()
    # Fast heartbeat interval of 0.2s for testing
    client = IpcClient(transport, token=TOKEN, reader_thread=True, heartbeat_interval_s=0.2)
    try:

        def answer_hello() -> None:
            f = transport.get_sent_frame()
            transport.put_response({"jsonrpc": "2.0", "id": f["id"], "result": BACKEND_INFO})

        threading.Thread(target=answer_hello).start()
        client.hello()

        # Within ~0.5s idle, client should send session.ping
        ping_frame = transport.get_sent_frame(timeout_s=2.0)
        assert ping_frame["method"] == "session.ping"
        transport.put_response({"jsonrpc": "2.0", "id": ping_frame["id"], "result": {"pong": True}})
    finally:
        client.close()
