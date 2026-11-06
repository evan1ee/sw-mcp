"""Test support for the core service: a rig over a temporary folder, and a file system that can
'crash'. Used by this package's tests; nothing in the service imports it."""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cad_application.config.settings import ConfigError
from cad_application.ports import BackendProvider, FileSystem, Lock
from cad_application.testing.fakes import SequentialIdSource
from cad_ir.core.json_types import JsonValue
from cad_protocol.replay import load_transcript

from core_service.os_fs import OsFileSystem
from core_service.providers import ReplayBackendProvider
from core_service.service import CoreService
from core_service.system_ids import SystemIdSource

FIXED_DRAWING: Final = "C:\\Work\\a.slddrw"  # the path the check_drawing transcripts hold
FINAL_STATES: Final = frozenset({"COMMITTED", "FAILED", "ABORTED"})
_WAIT_MS: Final = 5000
_MAX_POLLS: Final = 6
_HEAD: Final = 'config_version = "1.0"\n'


class CrashableFileSystem(OsFileSystem):
    """After ``crash()`` every mutation fails and every lock is gone, as for a dead process."""

    def __init__(self) -> None:
        super().__init__()
        self._dead = False
        self._held: list[Lock] = []

    def crash(self) -> None:
        self._dead = True
        for lock in self._held:
            lock.release()

    def _alive(self) -> None:
        if self._dead:
            raise OSError("the process is gone")

    def make_dirs(self, path: str) -> None:
        self._alive()
        super().make_dirs(path)

    def write_atomic(self, path: str, data: bytes) -> None:
        self._alive()
        super().write_atomic(path, data)

    def write_new(self, path: str, data: bytes) -> None:
        self._alive()
        super().write_new(path, data)

    def append_line(self, path: str, line: str) -> None:
        self._alive()
        super().append_line(path, line)

    def lock_exclusive(self, path: str) -> Lock:
        self._alive()
        lock = super().lock_exclusive(path)
        self._held.append(lock)
        return lock


def replay_provider(name: str, drawing_path: str, fixtures: Path) -> ReplayBackendProvider:
    """A provider for ``<name>.jsonl`` whose document path is replaced by ``drawing_path``."""
    text = (fixtures / f"{name}.jsonl").read_text(encoding="utf-8")
    old, new = json.dumps(FIXED_DRAWING)[1:-1], json.dumps(drawing_path)[1:-1]
    return ReplayBackendProvider(load_transcript(text.replace(old, new)))


@dataclass
class ServiceRig:
    """A started service over ``base``: user config allowing ``project``, one drawing in it."""

    base: Path
    project: Path
    drawing: str
    environ: Mapping[str, str]
    service: CoreService

    @staticmethod
    def environment(base: Path) -> dict[str, str]:
        return {"APPDATA": str(base / "appdata"), "LOCALAPPDATA": str(base / "local")}

    @classmethod
    def prepare(cls, base: Path, name: str = "a.slddrw", user_extra: str = "") -> tuple[Path, str]:
        """Folders, the user config file and the drawing; returns the project and drawing path."""
        project = base / "proj"
        project.mkdir(parents=True, exist_ok=True)
        drawing = project / name
        drawing.write_bytes(b"drawing-bytes")
        config = base / "appdata" / "sw-mcp"
        config.mkdir(parents=True, exist_ok=True)
        roots = f"[access]\nallowed_roots = ['{project}']\n"
        (config / "config.toml").write_text(_HEAD + roots + user_extra, encoding="utf-8")
        (base / "local").mkdir(exist_ok=True)
        return project, os.path.realpath(drawing)

    @classmethod
    def start(  # noqa: PLR0913 - one knob per thing a test varies
        cls,
        base: Path,
        provider: BackendProvider,
        *,
        project: Path,
        drawing: str,
        fs: FileSystem | None = None,
        sequential_ids: bool = True,
    ) -> "ServiceRig":
        environ = cls.environment(base)
        started = CoreService.start(
            install_root=str(base / "install"),
            environ=environ,
            provider=provider,
            fs=fs,
            ids=SequentialIdSource() if sequential_ids else SystemIdSource(),
        )
        if isinstance(started, ConfigError):
            raise AssertionError(started)
        return cls(base, project, drawing, environ, started)

    def call(self, name: str, arguments: JsonValue) -> dict[str, JsonValue]:
        envelope = self.service.call_tool(name, arguments).envelope
        if not isinstance(envelope, dict):
            raise AssertionError(envelope)
        return envelope

    def submit(self, sheets: list[str] | None = None) -> str:
        arguments: dict[str, JsonValue] = {"path": self.drawing}
        if sheets is not None:
            arguments["sheets"] = list(sheets)
        data = self.data(self.call("check_drawing", arguments))
        return str(data["execution_id"])

    def status(self, execution_id: str, wait_ms: int = 0) -> dict[str, JsonValue]:
        arguments: dict[str, JsonValue] = {"execution_id": execution_id, "wait_ms": wait_ms}
        return self.data(self.call("get_execution_status", arguments))

    def wait_final(self, execution_id: str) -> dict[str, JsonValue]:
        """Long-poll until the job is final; never sleeps."""
        data = self.status(execution_id)
        for _ in range(_MAX_POLLS):
            if data["state"] in FINAL_STATES:
                return data
            data = self.status(execution_id, _WAIT_MS)
        raise AssertionError(f"job did not finish: {data}")

    def wait_for_state(self, execution_id: str, state: str) -> None:
        data = self.status(execution_id)
        for _ in range(_MAX_POLLS):
            if data["state"] == state or data["state"] in FINAL_STATES:
                break
            data = self.status(execution_id, _WAIT_MS)
        assert data["state"] == state, data

    def journal(self, execution_id: str) -> list[dict[str, JsonValue]]:
        path = self.project / ".cad" / "jobs" / execution_id / "journal.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def snapshot_files(self) -> list[Path]:
        return list((self.project / ".cad" / "snapshots").rglob("*.json"))

    @staticmethod
    def data(envelope: dict[str, JsonValue]) -> dict[str, JsonValue]:
        data = envelope["data"]
        if envelope["ok"] is not True or not isinstance(data, dict):
            raise AssertionError(envelope)
        return data

    @staticmethod
    def error_code(envelope: dict[str, JsonValue]) -> str:
        error = envelope["error"]
        if envelope["ok"] is not False or not isinstance(error, dict):
            raise AssertionError(envelope)
        return str(error["code"])

    def stop(self) -> None:
        self.service.stop()
