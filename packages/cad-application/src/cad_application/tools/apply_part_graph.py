"""``apply_part_graph`` (spec 12.4.5, design 10): validate, authorize, store, queue plan."""

from typing import Final

from cad_compiler.validator.semantic import validate_graph
from cad_ir.core.issues import IssueReport, ValidationIssue
from cad_ir.core.json_types import JsonValue
from cad_ir.part_feature_graph.model import PartGraph
from cad_ir.part_feature_graph.parse import parse_part_graph

from cad_application.config.settings import ConfigError
from cad_application.jobs.model import PlanSpec
from cad_application.jobs.part_files import working_path
from cad_application.paths import Authorized, ToolError, authorize
from cad_application.store.errors import StoreError
from cad_application.tools.context import Call, ToolContext
from cad_application.tools.result import ToolResult, error, failure, ok
from cad_application.tools.summaries import part_queued_line

_SUFFIX: Final = ".sldprt"
_MAX_PATH_LEN: Final = 260
_DUMMY_JOB_ID: Final = "job_00000000000000000000000000"
_ISSUE_CAP: Final = 20


def _authorize(ctx: ToolContext, path: str) -> Authorized | ToolError:
    try:
        authorized = authorize(path, ctx.settings_user, ctx.fs, expect="new_file", suffix=_SUFFIX)
    except (OSError, ValueError):
        return ToolError(
            "AUTH_PATH_DENIED", "The path cannot be resolved.", {"reason": "invalid_path"}
        )
    if isinstance(authorized, ToolError):
        return authorized
    if len(working_path(authorized.path, _DUMMY_JOB_ID)) >= _MAX_PATH_LEN:
        return ToolError(
            "AUTH_PATH_DENIED",
            "The working file path would reach or exceed 260 characters.",
            {"reason": "path_too_long"},
        )
    return authorized


def _issues_error(call: Call, issues: tuple[ValidationIssue, ...]) -> ToolResult:
    errors = tuple(i for i in issues if i.severity == "error") or issues
    first = errors[0]
    shown: list[JsonValue] = [issue.to_json() for issue in issues[:_ISSUE_CAP]]
    details: dict[str, JsonValue] = {"issues": shown}
    if len(issues) > _ISSUE_CAP:
        details["omitted"] = len(issues) - _ISSUE_CAP
    return error(
        first.code.value,
        first.message,
        details,
        call.ids(),
        f"{first.code.value}: {first.pointer or '/'} {first.message}",
    )


def _config_error(problem: ConfigError, call: Call) -> ToolResult:
    details: dict[str, JsonValue] = {"origin": problem.origin}
    if problem.key is not None:
        details["key"] = problem.key
    if problem.line is not None:
        details["line"] = problem.line
    return error("CONFIG_INVALID", problem.message, details, call.ids())


def _validate_part(call: Call, raw_graph: JsonValue) -> PartGraph | ToolResult:
    parsed = parse_part_graph(raw_graph)
    if isinstance(parsed, IssueReport):
        return _issues_error(call, parsed.issues)
    semantic_issues = validate_graph(parsed)
    if any(i.severity == "error" for i in semantic_issues):
        return _issues_error(call, semantic_issues)
    return parsed


def _store_revision(
    ctx: ToolContext, call: Call, authorized: Authorized, part_id: str, raw_graph: JsonValue
) -> str | ToolResult:
    raw_rev = call.arguments.get("expected_revision")
    expected_revision = raw_rev if isinstance(raw_rev, int) else None
    settings = ctx.project_settings(authorized.project_root)
    if isinstance(settings, ConfigError):
        return _config_error(settings, call)
    store = ctx.stores.open_for(authorized)
    if isinstance(store, StoreError):
        return failure(store, call.ids())
    pinned_ref = store.put_part_revision(f"part:{part_id}", raw_graph, expected_revision)
    if isinstance(pinned_ref, StoreError):
        return failure(pinned_ref, call.ids())
    return pinned_ref


def handle(ctx: ToolContext, call: Call) -> ToolResult:
    raw_graph = call.arguments["graph"]
    target_path = call.arguments["target_path"]
    assert isinstance(target_path, str)

    parsed = _validate_part(call, raw_graph)
    if isinstance(parsed, ToolResult):
        return parsed

    authorized = _authorize(ctx, target_path)
    if isinstance(authorized, ToolError):
        return failure(authorized, call.ids())

    pinned_ref = _store_revision(ctx, call, authorized, parsed.id, raw_graph)
    if isinstance(pinned_ref, ToolResult):
        return pinned_ref

    view = ctx.engine.submit(
        PlanSpec(authorized=authorized, target_path=authorized.path, ref=pinned_ref),
        call.request_id,
    )
    if isinstance(view, StoreError):
        return failure(view, call.ids())

    position = view.queued_position or 0
    data: JsonValue = {
        "execution_id": view.job_id,
        "queued_position": position,
        "document": pinned_ref,
    }
    return ok(data, call.ids(execution_id=view.job_id), part_queued_line(view.job_id, position))
