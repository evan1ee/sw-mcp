"""A tool registry wired to the job rig's in-memory doubles, for handler tests."""

import ntpath
import threading
from collections.abc import Callable
from dataclasses import dataclass

from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import HelloResult

from cad_application.config.settings import ConfigError, Settings
from cad_application.ports import BackendUnavailable, Clock
from cad_application.testing.builders import PROJECT_ROOT
from cad_application.testing.fakes import FakeBackend
from cad_application.testing.job_rig import DRAWING, Rig, make_rig
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_application.tools.context import ToolContext
from cad_application.tools.registry import ToolRegistry, build_registry
from cad_application.tools.result import ToolResult

type ProjectSettings = Callable[[str], Settings | ConfigError]


def _envelope(result: ToolResult) -> dict[str, JsonValue]:
    envelope = result.envelope
    if not isinstance(envelope, dict):
        raise AssertionError(envelope)
    return envelope


@dataclass
class ToolRig:
    rig: Rig
    ctx: ToolContext
    registry: ToolRegistry

    def call(self, name: str, arguments: JsonValue) -> ToolResult:
        """One tool call with a fresh request ID, as the front-end makes it (ADR-041)."""
        return self.registry.call(name, arguments, self.rig.ids.new_id("req"))

    def write_drawing(self, path: str = DRAWING, content: bytes = b"drawing") -> None:
        self.rig.fs.make_dirs(ntpath.dirname(path))
        self.rig.fs.write_atomic(path, content)

    @staticmethod
    def data_of(result: ToolResult) -> dict[str, JsonValue]:
        envelope = _envelope(result)
        data = envelope["data"]
        if envelope["ok"] is not True or not isinstance(data, dict):
            raise AssertionError(envelope)
        return data

    @staticmethod
    def error_of(result: ToolResult) -> dict[str, JsonValue]:
        error = _envelope(result)["error"]
        if not isinstance(error, dict):
            raise AssertionError(result.envelope)
        return error

    @staticmethod
    def code_of(result: ToolResult) -> str | None:
        """The error code, or None for a success."""
        if _envelope(result)["ok"] is True:
            return None
        return str(ToolRig.error_of(result)["code"])

    @staticmethod
    def ids_of(result: ToolResult) -> dict[str, str]:
        ids = _envelope(result)["ids"]
        if not isinstance(ids, dict):
            raise AssertionError(ids)
        return {key: str(value) for key, value in ids.items()}


def make_tool_rig(  # noqa: PLR0913 - one knob per double, as in ``make_rig``
    *,
    snapshot: JsonValue = None,
    open_owned: bool = True,
    hello: HelloResult | None = None,
    clock: Clock | None = None,
    fs: MemoryFileSystem | None = None,
    unavailable: BackendUnavailable | None = None,
    backend: FakeBackend | None = None,
    block: threading.Event | None = None,
    project_settings: ProjectSettings | None = None,
) -> ToolRig:
    """Tools over fakes; ``C:\\Work`` is the one allowed root."""
    rig = make_rig(
        snapshot=snapshot,
        open_owned=open_owned,
        hello=hello,
        clock=clock,
        fs=fs,
        unavailable=unavailable,
        backend=backend,
        block=block,
    )
    settings = Settings(allowed_roots=(PROJECT_ROOT,))
    ctx = ToolContext(
        engine=rig.engine,
        stores=rig.stores,
        fs=rig.fs,
        clock=rig.clock,
        settings_user=settings,
        project_settings=project_settings or (lambda _root: settings),
        log=rig.log,
    )
    return ToolRig(rig, ctx, build_registry(ctx))
