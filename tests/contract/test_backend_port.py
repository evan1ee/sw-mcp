"""The Backend port (ADR-036): the IPC backend satisfies it, checked by pyright."""

from pathlib import Path

from cad_application.ports import Backend
from cad_protocol.replay import load_transcript, replay_backend

TRANSCRIPTS = Path(__file__).resolve().parents[1] / "fixtures" / "ipc"


def test_ipc_backend_is_a_backend() -> None:
    text = (TRANSCRIPTS / "snapshot_ok.jsonl").read_text(encoding="utf-8")
    backend: Backend = replay_backend(load_transcript(text))
    assert backend.session.solidworks.version == "2025"
    snapshot = backend.snapshot_drawing("C:/d/bracket.slddrw", ("Sheet1",))
    assert isinstance(snapshot, dict)
    assert snapshot["drawing"] == {"document": "bracket_dwg", "revision": 3}
