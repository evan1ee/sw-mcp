"""The front-end client survives a core restart (HANDOFF known issue)."""

import sys
import time
from pathlib import Path

import pytest
from core_service.providers import ReplayBackendProvider
from core_service.server.pipe_host import PipeHost
from core_service.service import CoreService
from core_service.testing import ServiceRig
from mcp_server.client import CorePipeClient

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows named pipes only")

ROOT = Path(__file__).resolve().parents[3]
IPC = ROOT / "tests" / "fixtures" / "ipc"


def _start_host(tmp_path: Path, tag: str) -> tuple[CoreService, PipeHost]:
    ServiceRig.prepare(tmp_path)
    service = CoreService.start(
        install_root=str(ROOT),
        environ=ServiceRig.environment(tmp_path),
        provider=ReplayBackendProvider.from_file(str(IPC / "check_drawing_borrowed.jsonl")),
    )
    assert isinstance(service, CoreService)
    host = PipeHost(
        service,
        pipe_name=f"test-reconnect-{tag}-{int(time.time() * 1000)}",
        token=f"token-{tag}",
        session_file=tmp_path / "local" / "sw-mcp" / "core.json",
    )
    host.start()
    return service, host


def test_client_reconnects_to_restarted_core(tmp_path: Path) -> None:
    service, host = _start_host(tmp_path, "a")
    client = CorePipeClient(
        session_file=tmp_path / "local" / "sw-mcp" / "core.json", auto_start=False
    )
    extra: list[tuple[CoreService, PipeHost]] = []
    try:
        client.connect()
        assert client.list_tools()

        # A restarted core publishes a new pipe and token; the old connection is gone.
        service_b, host_b = _start_host(tmp_path, "b")
        extra.append((service_b, host_b))
        client.close()

        assert client.list_tools()  # rediscovered through the session file, new token
        assert client._pipe_name == host_b._pipe_name  # pyright: ignore[reportPrivateUsage]
    finally:
        client.close()
        for svc, hst in [(service, host), *extra]:
            hst.stop()
            svc.stop()
