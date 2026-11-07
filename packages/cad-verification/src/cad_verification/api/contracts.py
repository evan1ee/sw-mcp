"""Per-operation verification contracts derived from Part Feature Graph IR (spec 10.2, ADR-064)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from cad_ir.core.canonical import content_hash
from cad_ir.core.json_types import JsonValue
from cad_ir.part_feature_graph.model import (
    CenterRectangle,
    CornerRectangle,
    PartGraph,
    SketchNode,
    StraightSlot,
)

type CheckStatus = Literal["passed", "failed", "warning", "not_applicable", "not_evaluated"]
type NotEvaluatedReason = Literal["not_executed", "unsupported", "missing_data", "malformed_data"]


@dataclass(frozen=True, slots=True)
class ContractCheck:
    """One check of a verification contract (schemas/execution-evidence/v0.json)."""

    name: str
    required: bool
    expected: JsonValue = None
    unit: str | None = None
    tolerance: JsonValue = None
    not_applicable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "name": self.name,
            "required": self.required,
        }
        if self.expected is not None:
            res["expected"] = self.expected
        if self.unit is not None:
            res["unit"] = self.unit
        if self.tolerance is not None:
            res["tolerance"] = self.tolerance
        if self.not_applicable_reason is not None:
            res["not_applicable_reason"] = self.not_applicable_reason
        return res


@dataclass(frozen=True, slots=True)
class VerificationContract:
    """Verification contract derived from an IR node (ADR-064)."""

    node: str
    level: str
    hash: str
    checks: tuple[ContractCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "level": self.level,
            "hash": self.hash,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass(frozen=True, slots=True)
class PostconditionResult:
    """One contract check evaluated against an operation's observation (ADR-064)."""

    name: str
    status: CheckStatus
    required: bool = True
    reason: str | None = None
    expected: JsonValue = None
    measured: JsonValue = None
    unit: str | None = None
    tolerance: JsonValue = None
    method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "name": self.name,
            "required": self.required,
            "status": self.status,
        }
        if self.reason is not None:
            res["reason"] = self.reason
        if self.expected is not None:
            res["expected"] = self.expected
        if self.measured is not None:
            res["measured"] = self.measured
        if self.unit is not None:
            res["unit"] = self.unit
        if self.tolerance is not None:
            res["tolerance"] = self.tolerance
        if self.method is not None:
            res["method"] = self.method
        return res


def _sketch_entity_count(sketch: SketchNode) -> int:
    """Number of segments this sketch produces in CAD."""
    count = 0
    for entity in sketch.entities.values():
        if isinstance(entity, (CornerRectangle, CenterRectangle, StraightSlot)):
            count += 4
        else:
            count += 1
    return count


def feature_contracts(graph: PartGraph) -> tuple[VerificationContract, ...]:
    """Derive T0-level verification contracts from IR nodes (ADR-064)."""
    contracts: list[VerificationContract] = []
    for node_id, node in graph.nodes.items():
        node_hash = content_hash(node.to_dict())
        checks: list[ContractCheck] = [
            ContractCheck(name="status_ok", required=True, expected=0),
            ContractCheck(name="not_suppressed", required=True, expected=False),
        ]
        if isinstance(node, SketchNode):
            checks.append(ContractCheck(name="type_matches", required=True, expected="sketch"))
            checks.append(
                ContractCheck(
                    name="entity_count", required=True, expected=_sketch_entity_count(node)
                )
            )
        else:
            checks.append(ContractCheck(name="type_matches", required=True, expected=node.type))

        contracts.append(
            VerificationContract(
                node=node_id,
                level="exact",
                hash=node_hash,
                checks=tuple(checks),
            )
        )
    return tuple(contracts)


def _eval_status_ok(
    check: ContractCheck, observation: Mapping[str, JsonValue]
) -> PostconditionResult:
    raw_warning = observation.get("is_warning")
    if raw_warning is not None and not isinstance(raw_warning, bool):
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=0,
            measured=raw_warning,
            status="not_evaluated",
            reason="malformed_data",
        )
    is_warning = bool(raw_warning)
    error_code = observation.get("error_code")
    if is_warning:
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=0,
            measured={"is_warning": is_warning, "error_code": error_code},
            status="warning",
        )
    if error_code is None:
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=0,
            measured=None,
            status="not_evaluated",
            reason="missing_data",
        )
    if isinstance(error_code, bool) or not isinstance(error_code, int):
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=0,
            measured=error_code,
            status="not_evaluated",
            reason="malformed_data",
        )
    if error_code != 0:
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=0,
            measured=error_code,
            status="failed",
        )
    return PostconditionResult(
        name=check.name,
        required=check.required,
        expected=0,
        measured=0,
        status="passed",
    )


def _eval_not_suppressed(
    check: ContractCheck, observation: Mapping[str, JsonValue]
) -> PostconditionResult:
    suppressed = observation.get("suppressed")
    if suppressed is None:
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=False,
            measured=None,
            status="not_evaluated",
            reason="missing_data",
        )
    if not isinstance(suppressed, bool):
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=False,
            measured=suppressed,
            status="not_evaluated",
            reason="malformed_data",
        )
    if suppressed is True:
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=False,
            measured=True,
            status="failed",
        )
    return PostconditionResult(
        name=check.name,
        required=check.required,
        expected=False,
        measured=False,
        status="passed",
    )


def _eval_exact_field(check: ContractCheck, measured: JsonValue) -> PostconditionResult:
    if measured is None:
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=check.expected,
            measured=None,
            status="not_evaluated",
            reason="missing_data",
        )
    if isinstance(check.expected, int) and not isinstance(check.expected, bool):
        if isinstance(measured, bool) or not isinstance(measured, int):
            return PostconditionResult(
                name=check.name,
                required=check.required,
                expected=check.expected,
                measured=measured,
                status="not_evaluated",
                reason="malformed_data",
            )
    elif isinstance(check.expected, str) and not isinstance(measured, str):
        return PostconditionResult(
            name=check.name,
            required=check.required,
            expected=check.expected,
            measured=measured,
            status="not_evaluated",
            reason="malformed_data",
        )
    status: CheckStatus = "passed" if measured == check.expected else "failed"
    return PostconditionResult(
        name=check.name,
        required=check.required,
        expected=check.expected,
        measured=measured,
        status=status,
    )


def evaluate(
    contract: VerificationContract,
    observation: Mapping[str, JsonValue] | None,
) -> tuple[PostconditionResult, ...]:
    """Judge contract checks against an operation observation (ADR-064)."""
    if observation is None:
        return tuple(
            PostconditionResult(
                name=check.name,
                required=check.required,
                expected=check.expected,
                measured=None,
                status="not_evaluated",
                reason="missing_data",
            )
            for check in contract.checks
        )

    results: list[PostconditionResult] = []
    for check in contract.checks:
        if check.name == "status_ok":
            results.append(_eval_status_ok(check, observation))
        elif check.name == "not_suppressed":
            results.append(_eval_not_suppressed(check, observation))
        elif check.name == "type_matches":
            results.append(_eval_exact_field(check, observation.get("type")))
        elif check.name == "entity_count":
            results.append(_eval_exact_field(check, observation.get("entity_count")))
        else:
            results.append(
                PostconditionResult(
                    name=check.name,
                    required=check.required,
                    expected=check.expected,
                    measured=observation.get(check.name),
                    status="not_evaluated",
                    reason="unsupported",
                )
            )

    return tuple(results)
