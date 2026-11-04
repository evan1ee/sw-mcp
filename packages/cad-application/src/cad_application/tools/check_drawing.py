"""``check_drawing`` (spec 12.4.5): validate, authorize, fingerprint, queue a job, return at once.

Everything that goes wrong after the job exists is the job's ``error``, not this call's.
"""

import hashlib
from typing import Final

from cad_ir.core.json_types import JsonValue

from cad_application.config.settings import ConfigError
from cad_application.jobs.model import CheckDrawingSpec
from cad_application.paths import Authorized, ToolError, authorize
from cad_application.store.errors import StoreError
from cad_application.tools.context import Call, ToolContext
from cad_application.tools.result import ToolResult, error, failure, ok
from cad_application.tools.summaries import queued_line

_SUFFIX: Final = ".slddrw"


def _unreadable() -> ToolError:
    return ToolError("FILE_NOT_FOUND", "The file cannot be read.", {"reason": "unreadable"})


def _authorize(ctx: ToolContext, path: str) -> Authorized | ToolError:
    try:
        return authorize(path, ctx.settings_user, ctx.fs, expect="file", suffix=_SUFFIX)
    except (OSError, ValueError):
        return ToolError(
            "AUTH_PATH_DENIED", "The path cannot be resolved.", {"reason": "invalid_path"}
        )


def _fingerprint(ctx: ToolContext, path: str) -> str | ToolError:
    """``sha256:`` of the file's bytes (13.1)."""
    try:
        data = ctx.fs.read_bytes(path)
    except OSError:
        return _unreadable()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _config_error(problem: ConfigError, call: Call) -> ToolResult:
    details: dict[str, JsonValue] = {"origin": problem.origin}
    if problem.key is not None:
        details["key"] = problem.key
    if problem.line is not None:
        details["line"] = problem.line
    return error("CONFIG_INVALID", problem.message, details, call.ids())


def _sheets(call: Call) -> tuple[str, ...] | None:
    sheets = call.arguments.get("sheets")
    if not isinstance(sheets, list):
        return None
    return tuple(name for name in sheets if isinstance(name, str))


def handle(ctx: ToolContext, call: Call) -> ToolResult:
    path = call.arguments["path"]
    assert isinstance(path, str)  # the input schema says so
    authorized = _authorize(ctx, path)
    if isinstance(authorized, ToolError):
        return failure(authorized, call.ids())
    fingerprint = _fingerprint(ctx, authorized.path)
    if isinstance(fingerprint, ToolError):
        return failure(fingerprint, call.ids())
    settings = ctx.project_settings(authorized.project_root)
    if isinstance(settings, ConfigError):
        return _config_error(settings, call)
    view = ctx.engine.submit(
        CheckDrawingSpec(authorized, fingerprint, _sheets(call)), call.request_id
    )
    if isinstance(view, StoreError):
        return failure(view, call.ids())
    position = view.queued_position or 0
    data: JsonValue = {"execution_id": view.job_id, "queued_position": position}
    return ok(data, call.ids(execution_id=view.job_id), queued_line(view.job_id, position))
