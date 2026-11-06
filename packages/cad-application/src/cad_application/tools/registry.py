"""The tool registry (spec 12.4.2): validate arguments, call the handler, check the contract.

A tool name with no contract is not a tool: ``call`` raises ``UnknownTool`` and the transport
answers a protocol error, never an envelope. After the handler returns, and always under
``python`` without ``-O``, the registry asserts what the contract promises: the envelope is
valid, an error code is listed in the contract, ``data`` satisfies ``output``, the summary fits.
"""

from collections.abc import Mapping
from functools import partial
from typing import Final

from cad_ir.core.issues import ValidationIssue
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated.error_codes import ErrorCode

from cad_application.tools import (
    apply_part_graph,
    cancel_execution,
    check_drawing,
    get_authoring_guide,
    get_drawing_report,
    get_execution_status,
    get_feature_schema,
    list_feature_types,
    validate_part_graph,
)
from cad_application.tools.context import Call, Handler, ToolContext
from cad_application.tools.contracts import ToolContract, load_contracts
from cad_application.tools.result import SUMMARY_MAX, Ids, ToolResult, error

ISSUE_CAP: Final = 20
ENVELOPE: Final = "https://sw-mcp.invalid/schemas/common/v0.json#/$defs/Envelope"


class UnknownTool(KeyError):  # noqa: N818 - the name is part of the contract of the registry
    """No contract file exists for this tool name."""


class ContractViolation(Exception):  # noqa: N818 - a defect in a handler, not a runtime condition
    """A handler returned something its contract does not allow."""


def _issue(message: str) -> ValidationIssue:
    return ValidationIssue(ErrorCode.IR_SCHEMA_INVALID, "", message)


def _schema_invalid(request_id: str, issues: tuple[ValidationIssue, ...]) -> ToolResult:
    shown: list[JsonValue] = [issue.to_json() for issue in issues[:ISSUE_CAP]]
    details: dict[str, JsonValue] = {"issues": shown}
    if len(issues) > ISSUE_CAP:
        details["omitted"] = len(issues) - ISSUE_CAP
    first = issues[0]
    return error(
        "IR_SCHEMA_INVALID",
        "The arguments do not satisfy the tool's input schema.",
        details,
        Ids(request_id),
        f"IR_SCHEMA_INVALID: {first.pointer or '/'} {first.message}",
    )


def _issues_of(contract: ToolContract, arguments: JsonValue) -> tuple[ValidationIssue, ...]:
    try:
        return validate_against_schema(arguments, contract.input_ref)
    except RecursionError:
        return (_issue("the arguments are nested too deeply"),)


class ToolRegistry:
    def __init__(
        self,
        contracts: Mapping[str, ToolContract],
        handlers: Mapping[str, Handler],
        *,
        verify: bool = __debug__,
    ) -> None:
        if set(contracts) != set(handlers):
            raise ValueError("every contract needs a handler and every handler a contract")
        self._contracts = contracts
        self._handlers = handlers
        self._verify = verify

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._contracts))

    def contract(self, name: str) -> ToolContract:
        found = self._contracts.get(name)
        if found is None:
            raise UnknownTool(name)
        return found

    def call(self, name: str, arguments: JsonValue, request_id: str) -> ToolResult:
        """Run one tool call. Bad arguments are an ``IR_SCHEMA_INVALID`` result, never raised."""
        contract = self.contract(name)
        issues = _issues_of(contract, arguments)
        if issues:
            return _schema_invalid(request_id, issues)
        if not isinstance(arguments, dict):
            return _schema_invalid(request_id, (_issue("the arguments must be an object"),))
        result = self._handlers[name](Call(request_id, arguments))
        if self._verify:
            _verify(contract, result)
        return result


def _verify(contract: ToolContract, result: ToolResult) -> None:
    envelope = result.envelope
    if validate_against_schema(envelope, ENVELOPE):
        raise ContractViolation(f"{contract.name}: the envelope is invalid")
    if len(result.summary) > SUMMARY_MAX or "\n" in result.summary:
        raise ContractViolation(f"{contract.name}: the summary is not one short line")
    if not isinstance(envelope, dict):
        raise ContractViolation(f"{contract.name}: the envelope is not an object")
    if envelope["ok"] is True:
        if validate_against_schema(envelope["data"], contract.output_ref):
            raise ContractViolation(f"{contract.name}: data does not satisfy output")
        return
    body = envelope["error"]
    code = body.get("code") if isinstance(body, dict) else None
    if code not in contract.errors:
        raise ContractViolation(f"{contract.name}: error code {code!r} is not listed")


def build_registry(context: ToolContext, *, verify: bool = __debug__) -> ToolRegistry:
    """The registry of the shipped tools, bound to one set of services."""
    handlers: dict[str, Handler] = {
        "apply_part_graph": partial(apply_part_graph.handle, context),
        "cancel_execution": partial(cancel_execution.handle, context),
        "check_drawing": partial(check_drawing.handle, context),
        "get_drawing_report": partial(get_drawing_report.handle, context),
        "get_execution_status": partial(get_execution_status.handle, context),
        "get_feature_schema": partial(get_feature_schema.handle, context),
        "get_authoring_guide": partial(get_authoring_guide.handle, context),
        "list_feature_types": partial(list_feature_types.handle, context),
        "validate_part_graph": partial(validate_part_graph.handle, context),
    }
    return ToolRegistry(load_contracts(), handlers, verify=verify)
