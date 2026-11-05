"""Feature lowering from resolved graph to backend operations (spec 6.5.2, 6.7.2)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from cad_ir.core.issues import ValidationIssue
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph.model import Line, PartGraph, SketchNode, SolidNode

from cad_compiler.graph.analyze import GraphAnalysis
from cad_compiler.profile import CapabilityProfile

WORKING: Final[str] = "$working"
STANDARD_PLANES: Final[frozenset[str]] = frozenset({"plane:front", "plane:top", "plane:right"})


@dataclass(frozen=True, slots=True)
class LoweringResult:
    """Operations and verification points resulting from lowering."""

    operations: dict[str, dict[str, Any]]
    verification_points: list[str]
    defaults_applied: dict[str, Any]


def _check_capabilities(graph: PartGraph, profile: CapabilityProfile) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not profile.supports_operation("part.create"):
        issues.append(
            ValidationIssue(
                code=ErrorCode.BACKEND_CAPABILITY_MISSING,
                pointer="/operations",
                message="Backend lacks capability for 'part.create'",
            )
        )
    for node_id, node in graph.nodes.items():
        if not profile.supports_feature(node.type, "create"):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.COMPILE_UNSUPPORTED_FEATURE,
                    pointer=f"/nodes/{node_id}/type",
                    message=f"Feature '{node.type}' unsupported by capability profile",
                )
            )
        if isinstance(node, SketchNode):
            if node.plane not in STANDARD_PLANES:
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.COMPILE_UNSUPPORTED_FEATURE,
                        pointer=f"/nodes/{node_id}/plane",
                        message=f"Plane '{node.plane}' unsupported; standard planes required",
                    )
                )
            if not profile.supports_operation("sketch.create"):
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.BACKEND_CAPABILITY_MISSING,
                        pointer=f"/nodes/{node_id}",
                        message="Backend lacks capability for 'sketch.create'",
                    )
                )
        elif not profile.supports_operation("feature.create"):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.BACKEND_CAPABILITY_MISSING,
                    pointer=f"/nodes/{node_id}",
                    message="Backend lacks capability for 'feature.create'",
                )
            )
    return issues


def _lower_sketch(node_id: str, node: SketchNode, seq: int, deps: list[str]) -> dict[str, Any]:
    entities_list: list[dict[str, Any]] = []
    for ent_id in sorted(node.entities.keys()):
        ent = node.entities[ent_id]
        if isinstance(ent, Line):
            entities_list.append(
                {
                    "type": "line",
                    "start": [float(ent.start[0]), float(ent.start[1])],
                    "end": [float(ent.end[0]), float(ent.end[1])],
                }
            )
        else:
            entities_list.append(
                {
                    "type": "circle",
                    "center": [float(ent.center[0]), float(ent.center[1])],
                    "diameter": float(ent.diameter),
                }
            )
    return {
        "sequence": seq,
        "document": WORKING,
        "op": "sketch.create",
        "params": {
            "node_id": node_id,
            "plane": node.plane,
            "entities": entities_list,
        },
        "source": node_id,
        "depends_on": deps,
        "postconditions": ["entity_count"],
    }


def _lower_solid(
    node_id: str, node: SolidNode, seq: int, deps: list[str]
) -> tuple[dict[str, Any], str]:
    end_cond: dict[str, Any] = {"type": node.end_condition.type}
    if node.end_condition.depth is not None:
        end_cond["depth"] = float(node.end_condition.depth)

    params: dict[str, Any] = {
        "node_id": node_id,
        "type": node.type,
        "profile": node.profile,
        "end_condition": end_cond,
    }

    op_id = f"op_{seq}"
    op_body = {
        "sequence": seq,
        "document": WORKING,
        "op": "feature.create",
        "params": params,
        "source": node_id,
        "depends_on": deps,
        "postconditions": ["feature_exists", "feature_status_ok", "rebuild_ok"],
    }
    return op_body, op_id


def lower_graph(
    graph: PartGraph,
    analysis: GraphAnalysis,
    profile: CapabilityProfile,
    defaults: Mapping[str, Any],
) -> tuple[LoweringResult | None, list[ValidationIssue]]:
    """Lower a validated PartGraph into Execution Plan operations."""
    issues = _check_capabilities(graph, profile)
    if issues:
        return None, issues

    operations: dict[str, dict[str, Any]] = {}
    verification_points: list[str] = []
    defaults_applied: dict[str, Any] = {}
    node_to_op_id: dict[str, str] = {}

    op1_id = "op_1"
    operations[op1_id] = {
        "sequence": 1,
        "document": WORKING,
        "op": "part.create",
        "params": {},
        "source": None,
        "depends_on": [],
        "postconditions": [],
    }

    seq = 2
    for node_id in analysis.order:
        node = graph.nodes[node_id]
        op_id = f"op_{seq}"
        node_to_op_id[node_id] = op_id

        direct_deps = analysis.dependencies.get(node_id, frozenset())
        dep_op_ids = [node_to_op_id[d] for d in sorted(direct_deps) if d in node_to_op_id] or [
            op1_id
        ]

        if isinstance(node, SketchNode):
            operations[op_id] = _lower_sketch(node_id, node, seq, dep_op_ids)
        else:
            op_body, vp_id = _lower_solid(node_id, node, seq, dep_op_ids)
            operations[op_id] = op_body
            verification_points.append(vp_id)

        seq += 1

    return LoweringResult(
        operations=operations,
        verification_points=verification_points,
        defaults_applied=defaults_applied,
    ), []
