"""Record a real plate job against the open SOLIDWORKS as an IPC transcript (spec 15.5).

Drives one ``apply_part_graph`` job through a recording transport and writes the add-in
conversation to ``tests/fixtures/ipc/plan_plate_live_recorded.jsonl``. It uses whichever
SOLIDWORKS instance has the add-in loaded, so run it only on a throwaway instance.

    uv run python scripts/record_plate_transcript.py <scratch_dir>
"""

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

from cad_protocol.client.pipe_transport import NamedPipeTransport
from cad_protocol.client.transport import Transport, TransportClosed
from core_service.discovery import NamedPipeBackendProvider

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "ipc" / "plan_plate_live_recorded.jsonl"
SCENARIO = "plan_plate_live_recorded"
TOKEN = "tok-recorded"


class RecordingTransport(Transport):
    """Pass frames through and keep a timeline of them."""

    def __init__(self, inner: Transport, entries: list[dict[str, Any]], start: float) -> None:
        self._inner = inner
        self._entries = entries
        self._start = start
        self._lock = threading.Lock()

    def _note(self, direction: str, payload: bytes | None) -> None:
        with self._lock:
            entry: dict[str, Any] = {
                "dir": direction,
                "t_ms": int((time.monotonic() - self._start) * 1000),
            }
            if payload is None:
                entry["close"] = True
            else:
                frame = json.loads(payload)
                if frame.get("method") == "session.hello":
                    frame["params"]["token"] = TOKEN
                entry["frame"] = frame
            self._entries.append(entry)

    def send(self, payload: bytes) -> None:
        self._note("core_to_addin", payload)
        self._inner.send(payload)

    def receive(self, timeout_s: float) -> bytes:
        try:
            payload = self._inner.receive(timeout_s)
        except TransportClosed:
            self._note("addin_to_core", None)
            raise
        self._note("addin_to_core", payload)
        return payload

    def close(self) -> None:
        self._inner.close()


def _load_live_helpers() -> Any:
    path = ROOT / "tests" / "live" / "test_live_part_chain.py"
    spec = importlib.util.spec_from_file_location("live_part_chain", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["live_part_chain"] = module
    spec.loader.exec_module(module)
    return module


def main(scratch: Path) -> None:
    live = _load_live_helpers()
    session = live._get_live_session()
    template = live._resolve_template()
    entries: list[dict[str, Any]] = []
    start = time.monotonic()
    provider = NamedPipeBackendProvider(
        target_session=str(session.pid),
        transport_factory=lambda pipe: RecordingTransport(NamedPipeTransport(pipe), entries, start),
    )
    proj = scratch / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    target = proj / "plate_recorded.SLDPRT"
    service = live._start_core(
        scratch, allowed_roots=(proj,), template_path=template, provider=provider
    )
    try:
        applied = live._call_ok(
            service, "apply_part_graph", {"graph": live._plate_graph(), "target_path": str(target)}
        )
        final = live._wait_for_job(service, str(applied["execution_id"]))
    finally:
        service.stop()
    if final["state"] != "COMMITTED":
        raise SystemExit(f"job ended {final['state']}: not recording a failed run")

    hello = next(e for e in entries if e["dir"] == "addin_to_core")["frame"]["result"]
    header = {
        "transcript": "0.1",
        "scenario": SCENARIO,
        "source": "recorded",
        "sides": ["python"],
        "config": {"token": TOKEN, "backend": hello, "version_supported": True},
    }
    lines = [json.dumps(header, ensure_ascii=False)]
    lines += [json.dumps(e, ensure_ascii=False) for e in entries]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"recorded {len(entries)} frames to {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
