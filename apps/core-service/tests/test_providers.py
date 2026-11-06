"""ReplayBackendProvider: a transcript behind the BackendProvider port."""

from pathlib import Path

import pytest
from cad_application.ports import BackendUnavailable
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import Operation, OperationGroup
from cad_protocol.replay import Transcript, load_transcript, replay_backend
from core_service.providers import ReplayBackendProvider

IPC = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ipc"
WORK = "C:\\Work\\a.slddrw"


def _transcript(name: str) -> Transcript:
    return load_transcript((IPC / f"{name}.jsonl").read_text(encoding="utf-8"))


def test_replay_backend_passes_notifications() -> None:
    seen: list[tuple[str, JsonValue]] = []
    backend = replay_backend(
        _transcript("check_drawing_ui_blocked"),
        on_notification=lambda method, params: seen.append((method, params)),
    )
    open_op = Operation(
        operation_id="job_00000000000000000000000001:1",
        op="document.open",
        params={"path": WORK, "read_only": True, "fully_resolved": True},
    )
    backend.apply_ops([OperationGroup(document=WORK, operations=(open_op,))])
    backend.snapshot_drawing(WORK)
    assert seen == [("session.ui_blocked", {"waited_ms": 30000})]


def test_replay_backend_default_has_no_notification_handler() -> None:
    backend = replay_backend(_transcript("handshake"))
    assert backend.session.addin_version == "0.1.0"


def test_provider_acquires_a_fresh_session_each_time() -> None:
    provider = ReplayBackendProvider(_transcript("handshake"))
    first = provider.acquire(lambda _m, _p: None)
    second = provider.acquire(lambda _m, _p: None)
    assert first is not second
    assert second.session.addin_version == "0.1.0"


def test_provider_translates_a_closed_pipe_during_the_handshake() -> None:
    lines = (IPC / "handshake.jsonl").read_text(encoding="utf-8").splitlines()
    closed = "\n".join([*lines[:2], '{"dir":"addin_to_core","t_ms":30,"close":true}'])
    provider = ReplayBackendProvider(load_transcript(closed))
    with pytest.raises(BackendUnavailable) as info:
        provider.acquire(lambda _m, _p: None)
    assert info.value.code == "BACKEND_LOST"
    assert "tok-5f2c91d7" not in str(info.value)


def test_provider_unsupported_version_keeps_its_code() -> None:
    provider = ReplayBackendProvider(_transcript("solidworks_unsupported"))
    with pytest.raises(BackendUnavailable) as info:
        provider.acquire(lambda _m, _p: None)
    assert info.value.code == "BACKEND_VERSION_UNSUPPORTED"


def test_provider_missing_transcript_file_is_backend_lost(tmp_path: Path) -> None:
    provider = ReplayBackendProvider.from_file(str(tmp_path / "nope.jsonl"))
    with pytest.raises(BackendUnavailable) as info:
        provider.acquire(lambda _m, _p: None)
    assert info.value.code == "BACKEND_LOST"


@pytest.mark.parametrize(
    "content", [b"", b"\x00\xff\xfe binary", b"not json\n", b'{"transcript": "9"}\n']
)
def test_provider_unreadable_transcript_is_backend_lost(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_bytes(content)
    with pytest.raises(BackendUnavailable) as info:
        ReplayBackendProvider.from_file(str(path)).acquire(lambda _m, _p: None)
    assert info.value.code == "BACKEND_LOST"


def test_provider_reads_a_transcript_file(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_bytes((IPC / "handshake.jsonl").read_bytes())
    backend = ReplayBackendProvider.from_file(str(path)).acquire(lambda _m, _p: None)
    assert backend.session.addin_version == "0.1.0"
