"""Lifecycle tests for backends, ports, error handling, reconnect, and framing."""

import io
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from cad_application.ports import Backend, BackendUnavailable
from cad_application.testing.fakes import FakeBackend, make_hello
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import Operation, OperationGroup
from cad_protocol.client.transport import Transport, TransportClosed, TransportTimeout
from cad_protocol.framing import encode_frame, read_frame
from cad_protocol.replay import Transcript, load_transcript, replay_backend
from core_service.discovery import NamedPipeBackendProvider
from core_service.reconcile import ReconcilingProvider


class _MockTransport(Transport):
    def __init__(self, responses: list[bytes] | None = None) -> None:
        self.closed = False
        self.sent: list[bytes] = []
        self._pending_responses = list(responses or [])
        self._queue: list[bytes] = []
        self._cv = threading.Condition()

    def send(self, payload: bytes) -> None:
        with self._cv:
            if self.closed:
                raise TransportClosed("closed")
            self.sent.append(payload)
            if self._pending_responses:
                self._queue.append(self._pending_responses.pop(0))
                self._cv.notify_all()

    def receive(self, timeout_s: float) -> bytes:
        with self._cv:
            if self.closed:
                raise TransportClosed("closed")
            if self._queue:
                return self._queue.pop(0)
            self._cv.wait(timeout_s)
            if self.closed:
                raise TransportClosed("closed")
            if self._queue:
                return self._queue.pop(0)
            raise TransportTimeout("no data")

    def close(self) -> None:
        with self._cv:
            self.closed = True
            self._cv.notify_all()


def test_backend_protocol_has_measure_part_and_close() -> None:
    # Verify that Backend protocol includes measure_part and close
    assert hasattr(Backend, "measure_part")
    assert hasattr(Backend, "close")


def test_fake_backend_supports_measure_and_close() -> None:
    fake = FakeBackend(make_hello())
    assert hasattr(fake, "measure_part")
    assert hasattr(fake, "close")

    # Scripted measurement
    expected_m: JsonValue = {
        "path": "D:\\test.SLDPRT",
        "volume_m3": 0.001,
    }
    fake_with_m = FakeBackend(make_hello(), snapshot=None, measurement=expected_m)
    measured = fake_with_m.measure_part("D:\\test.SLDPRT")
    assert measured == expected_m

    # Scripted op_results
    fake_with_ops = FakeBackend(
        make_hello(), op_results={"part.create": {"native_id": 1, "path": "p"}}
    )
    res = fake_with_ops.apply_ops(
        [
            OperationGroup(
                document="d",
                operations=(Operation(operation_id="op1", op="part.create"),),
            )
        ]
    )
    assert res.outcomes[0].result == {"native_id": 1, "path": "p"}

    fake.close()
    assert fake.closed


def test_measure_round_trip_synthetic_transcript() -> None:
    raw_path = "D:\\work\\plate.SLDPRT"
    sw_info = {"version": "2025", "service_pack": "SP3.0", "ui_language": "en-US"}
    header = json.dumps(
        {
            "transcript": "0.1",
            "scenario": "measure_ok",
            "source": "synthetic",
            "sides": ["python"],
            "config": {
                "token": "tok-test",
                "backend": {
                    "protocol": "0.1",
                    "addin_version": "0.1.0",
                    "solidworks": sw_info,
                    "capabilities": ["part.measure"],
                    "operations": [],
                    "licensed_modules": [],
                    "warnings": [],
                },
                "version_supported": True,
            },
        }
    )
    f1 = json.dumps(
        {
            "dir": "core_to_addin",
            "t_ms": 0,
            "frame": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "session.hello",
                "params": {"token": "tok-test", "protocol": "0.1"},
            },
        }
    )
    f2 = json.dumps(
        {
            "dir": "addin_to_core",
            "t_ms": 20,
            "frame": {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocol": "0.1",
                    "addin_version": "0.1.0",
                    "solidworks": sw_info,
                    "capabilities": ["part.measure"],
                    "operations": [],
                    "licensed_modules": [],
                    "warnings": [],
                },
            },
        }
    )
    f3 = json.dumps(
        {
            "dir": "core_to_addin",
            "t_ms": 50,
            "frame": {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "part.measure",
                "params": {"document": raw_path},
            },
        }
    )
    f4 = json.dumps(
        {
            "dir": "addin_to_core",
            "t_ms": 70,
            "frame": {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "path": raw_path,
                    "volume_m3": 5.798938e-05,
                    "rebuild": {"ok": True, "errors": []},
                },
            },
        }
    )
    transcript_text = "\n".join([header, f1, f2, f3, f4]) + "\n"
    transcript: Transcript = load_transcript(transcript_text)
    backend = replay_backend(transcript)

    result = backend.measure_part(raw_path)
    assert result == {
        "path": raw_path,
        "volume_m3": 5.798938e-05,
        "rebuild": {"ok": True, "errors": []},
    }


def test_failed_handshake_closes(tmp_path: Path) -> None:
    # An IpcError from IpcBackend(client) closes the client and transport
    hello_err_reply = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32000,
                "message": "Addin crashed",
                "data": {
                    "code": "BACKEND_LOST",
                    "message": "Addin crashed",
                    "retryable": "after_fix",
                    "details": {},
                },
            },
        }
    ).encode()
    transport = _MockTransport([hello_err_reply])

    session_content = json.dumps(
        {
            "pipe": "pipe",
            "token": "tok",
            "pid": 123,
            "solidworks": {},
            "addin_version": "0.1",
            "protocol": "0.1",
            "started_at": "",
        }
    )
    (tmp_path / "123.json").write_text(session_content, encoding="utf-8")
    provider = NamedPipeBackendProvider(
        session_dir=tmp_path,
        is_process_running=lambda _: True,
        transport_factory=lambda _: transport,
    )

    with pytest.raises(BackendUnavailable) as exc:
        provider.acquire(lambda _m, _p: None)
    assert exc.value.code == "BACKEND_LOST"
    assert transport.closed


def test_failed_reconcile_closes() -> None:
    # If reconcile fails, the acquired backend must be closed, and the next acquire works
    class _FailingEngine:
        def reconcile_pending(self) -> bool:
            return True

        def reconcile(self, backend: Any) -> None:
            raise RuntimeError("reconcile boom")

    class _InnerProvider:
        def __init__(self) -> None:
            self.backends: list[FakeBackend] = []

        def acquire(self, on_notification: Any) -> Backend:
            b = FakeBackend(make_hello())
            self.backends.append(b)
            return b

    inner = _InnerProvider()
    reconciler = ReconcilingProvider(inner)
    engine = _FailingEngine()
    reconciler.arm(engine)  # type: ignore[arg-type]

    # First acquire fails during reconcile
    with pytest.raises(RuntimeError, match="reconcile boom"):
        reconciler.acquire(lambda _m, _p: None)

    # The first backend was closed
    assert len(inner.backends) == 1
    assert inner.backends[0].closed

    # Next acquire works after engine is disarmed/healthy
    class _HealthyEngine:
        def reconcile_pending(self) -> bool:
            return False

        def reconcile(self, backend: Any) -> None:
            pass

    reconciler.arm(_HealthyEngine())  # type: ignore[arg-type]
    b2 = reconciler.acquire(lambda _m, _p: None)
    backend_count = 2
    assert len(inner.backends) == backend_count
    assert b2 is inner.backends[1]
    assert not inner.backends[1].closed


def test_reconnect_waits(tmp_path: Path) -> None:
    # A connect during the add-in's gap succeeds within the bound (using Task 1 spike result)
    hello_reply = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocol": "0.1",
                "addin_version": "0.1.0",
                "solidworks": {"version": "2025", "service_pack": "SP3.0", "ui_language": "en-US"},
                "capabilities": ["part.measure"],
                "operations": [],
                "licensed_modules": [],
                "warnings": [],
            },
        }
    ).encode()

    attempts = 0
    max_gap_attempts = 3

    def fake_factory(pipe_path: str) -> Transport:
        del pipe_path
        nonlocal attempts
        attempts += 1
        if attempts < max_gap_attempts:
            raise TransportClosed("Gap: server not ready yet")
        return _MockTransport([hello_reply])

    # Session file exists
    session_file = tmp_path / "1234.json"
    session_content = json.dumps(
        {
            "pipe": "test_pipe",
            "token": "tok",
            "pid": 1234,
            "solidworks": {},
            "addin_version": "0.1",
            "protocol": "0.1",
            "started_at": "",
        }
    )
    session_file.write_text(session_content, encoding="utf-8")

    times = [0.0, 0.03, 0.06, 0.09]
    t_idx = 0

    def mock_monotonic() -> float:
        nonlocal t_idx
        val = times[min(t_idx, len(times) - 1)]
        t_idx += 1
        return val

    def mock_sleep(_s: float) -> None:
        pass

    provider = NamedPipeBackendProvider(
        session_dir=tmp_path,
        is_process_running=lambda _: True,
        reconnect_timeout_s=2.0,
        reconnect_poll_s=0.03,
        monotonic=mock_monotonic,
        sleep=mock_sleep,
        transport_factory=fake_factory,
    )

    backend = provider.acquire(lambda _m, _p: None)
    assert attempts == max_gap_attempts
    assert backend.session.protocol == "0.1"


def test_non_ascii_round_trip() -> None:
    # Test D:\零件\板.SLDPRT through Python framing transcript unchanged
    non_ascii_path = "D:\\零件\\板.SLDPRT"
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "part.measure",
            "params": {"document": non_ascii_path},
        },
        ensure_ascii=False,
    ).encode("utf-8")

    frame = encode_frame(payload)
    stream = io.BytesIO(frame)
    decoded_payload = read_frame(stream)
    assert decoded_payload is not None
    assert decoded_payload.decode("utf-8") == payload.decode("utf-8")
    parsed = json.loads(decoded_payload)
    assert parsed["params"]["document"] == non_ascii_path
    assert "零件" in decoded_payload.decode("utf-8")
    assert "板" in decoded_payload.decode("utf-8")
