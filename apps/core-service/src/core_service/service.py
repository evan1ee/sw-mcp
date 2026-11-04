"""The core service: composition root, tool entry point and the one worker thread (ADR-041,
ADR-053).

``CoreService.start`` reads the configuration, opens the known stores, recovers interrupted jobs
(13.2.3) and starts the worker. ``call_tool`` is the in-process entry the transport will call
(milestone 6); it answers every input with a ``ToolResult``. The one exception it lets through is
``ContractViolation``: a handler that breaks its contract is a defect, not an input problem.
"""

import threading
from collections.abc import Callable, Mapping
from typing import Final, cast

from cad_application.config import load_title_block_mappings
from cad_application.config.settings import ConfigError, Settings
from cad_application.jobs.engine import JobEngine
from cad_application.ports import BackendProvider, Clock, EventLog, FileSystem, IdSource
from cad_application.store.store_set import StoreSet
from cad_application.tools.context import ToolContext
from cad_application.tools.registry import (
    ToolRegistry,
    UnknownTool,
    build_registry,
)
from cad_application.tools.result import Ids, ToolResult, error
from cad_drawing.checks import TitleBlockMapping
from cad_ir.core.json_types import JsonValue

from core_service.config_loader import CoreConfig, ProjectSettings, load_core_config
from core_service.jsonl_log import JsonlEventLog
from core_service.os_fs import OsFileSystem
from core_service.reconcile import ReconcilingProvider
from core_service.system_clock import SystemClock
from core_service.system_ids import SystemIdSource

_POLL_S: Final = 0.25
_JOIN_S: Final = 5.0


class CoreService:
    def __init__(
        self,
        engine: JobEngine,
        registry: ToolRegistry,
        stores: StoreSet,
        ids: IdSource,
        log: EventLog,
    ) -> None:
        self._engine = engine
        self._registry = registry
        self._stores = stores
        self._ids = ids
        self._log = log
        self._stopping = threading.Event()
        self._stop_guard = threading.Lock()
        self._stopped = False
        self._worker = threading.Thread(target=self._work, name="core-worker", daemon=True)

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @classmethod
    def start(  # noqa: PLR0913 - the injectable parts; defaults are the real ones
        cls,
        *,
        install_root: str,
        environ: Mapping[str, str],
        provider: BackendProvider,
        fs: FileSystem | None = None,
        clock: Clock | None = None,
        ids: IdSource | None = None,
        log: EventLog | None = None,
    ) -> "CoreService | ConfigError":
        """Refuses to start (returns the ``ConfigError``) on an invalid user file or environment."""
        fs, clock, ids = fs or OsFileSystem(), clock or SystemClock(), ids or SystemIdSource()
        config = load_core_config(fs, environ, install_root)
        if isinstance(config, ConfigError):
            return config
        log = log or _file_log(config, clock)
        stores = StoreSet(fs, clock, config.known_stores_path)
        project = ProjectSettings(fs, config)
        reconciling = ReconcilingProvider(provider)
        engine = JobEngine(
            stores,
            reconciling,
            clock,
            ids,
            log,
            _settings_for(project, config),
            _mappings_for(fs, log),
        )
        engine.recover_all()
        reconciling.arm(engine)
        context = ToolContext(engine, stores, fs, clock, config.settings, project, log)
        service = cls(engine, build_registry(context), stores, ids, log)
        service._worker.start()
        return service

    def call_tool(self, name: object, arguments: object) -> ToolResult:
        """Run one tool call. Bad input and store I/O failures are catalogued error results.

        Protocol errors are raised for the transport (12.4.2, J13, J14): ``UnknownTool`` for a
        name with no contract (a non-string included) and any unexpected exception, which is a
        defect; its class name is logged, nothing else."""
        request_id = self._ids.new_id("req")
        if not isinstance(name, str):
            raise UnknownTool(repr(type(name).__name__))
        try:
            result = self._registry.call(name, cast("JsonValue", arguments), request_id)
        except UnicodeError:
            return self._failed(request_id, "IR_SCHEMA_INVALID", "unencodable_text", name)
        except OSError as problem:
            return self._failed(request_id, "STORE_UNAVAILABLE", "io_error", name, problem)
        except UnknownTool:
            raise
        except Exception as problem:
            self._log.emit(
                "tool.error", "error", request_id=request_id, reason=type(problem).__name__
            )
            raise
        self._log.emit("tool.result", "info", request_id=request_id, tool=name)
        return result

    def stop(self, timeout_s: float = _JOIN_S) -> None:
        """Stop the worker and release the stores. A job still running after ``timeout_s`` is
        left as it is: the next start recovers it like a crash (13.2.3)."""
        with self._stop_guard:
            if self._stopped:
                return
            self._stopped = True
        self._stopping.set()
        self._worker.join(timeout_s)
        self._stores.close_all()

    def _work(self) -> None:
        while not self._stopping.is_set():
            try:
                if self._engine.wait_for_work(_POLL_S):
                    self._engine.run_next()
            except Exception as problem:
                self._log.emit("worker.error", "error", reason=type(problem).__name__)

    def _failed(
        self,
        request_id: str,
        code: str,
        reason: str,
        tool: str,
        problem: Exception | None = None,
    ) -> ToolResult:
        name = type(problem).__name__ if problem is not None else reason
        self._log.emit("tool.error", "error", request_id=request_id, error_code=code, reason=name)
        messages = {
            "io_error": "A project store file cannot be read or written.",
            "unencodable_text": "The arguments hold text that cannot be stored.",
        }
        return error(code, messages[reason], {"reason": reason}, Ids(request_id))


def _file_log(config: CoreConfig, clock: Clock) -> EventLog:
    return JsonlEventLog(
        config.logs_dir,
        "core",
        clock,
        level=config.settings.logging_level,
        retention_days=config.settings.logging_retention_days,
    )


def _settings_for(project: ProjectSettings, config: CoreConfig) -> Callable[[str], Settings]:
    def settings_for(project_root: str) -> Settings:
        found = project(project_root)
        return config.settings if isinstance(found, ConfigError) else found

    return settings_for


def _mappings_for(
    fs: FileSystem, log: EventLog
) -> Callable[[Settings], Mapping[str, TitleBlockMapping]]:
    def mappings_for(settings: Settings) -> Mapping[str, TitleBlockMapping]:
        found = load_title_block_mappings(fs, settings.standard_dir)
        if isinstance(found, ConfigError):
            log.emit("config.invalid", "warning", reason="title_block_mapping")
            return {}
        return found

    return mappings_for
