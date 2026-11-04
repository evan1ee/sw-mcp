"""What a handler is given: the call and the services it may use (spec 12.4.2)."""

from collections.abc import Callable
from dataclasses import dataclass

from cad_ir.core.json_types import JsonValue

from cad_application.config.settings import ConfigError, Settings
from cad_application.jobs.engine import JobEngine
from cad_application.ports import Clock, EventLog, FileSystem
from cad_application.store.store_set import StoreSet
from cad_application.tools.result import Ids, ToolResult


@dataclass(frozen=True, slots=True)
class Call:
    """One validated call: the front-end's request ID and arguments that satisfy ``input``."""

    request_id: str
    arguments: dict[str, JsonValue]

    def ids(self, *, execution_id: str | None = None, report_id: str | None = None) -> Ids:
        return Ids(self.request_id, execution_id, report_id)


@dataclass(frozen=True, slots=True)
class ToolContext:
    """The services of the core. ``settings_user`` decides which paths are allowed (12.5);
    ``project_settings`` merges a project's own file for a project folder (13.3.2)."""

    engine: JobEngine
    stores: StoreSet
    fs: FileSystem
    clock: Clock
    settings_user: Settings
    project_settings: Callable[[str], Settings | ConfigError]
    log: EventLog


type Handler = Callable[[Call], ToolResult]
