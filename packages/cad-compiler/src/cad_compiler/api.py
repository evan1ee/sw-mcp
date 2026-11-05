"""CAD Compiler API and 6.7 Pipeline Stages (spec 6.5.3, 6.7)."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Literal

from cad_ir.bundle.manifest import BundleManifest
from cad_ir.core.issues import IssueReport, ValidationIssue
from cad_ir.core.json_types import JsonValue
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph.model import PartGraph, SketchNode
from cad_ir.part_feature_graph.parse import parse_part_graph

from cad_compiler.graph.analyze import GraphAnalysis, analyze_graph, build_order
from cad_compiler.lowering.lower import STANDARD_PLANES, WORKING, LoweringResult, lower_graph
from cad_compiler.planner.plan import build_plan
from cad_compiler.profile import CapabilityProfile
from cad_compiler.validator.semantic import validate_graph

STAGE_VERSIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "parser": "0.1.0",
        "schema_validator": "0.1.0",
        "semantic_validator": "0.1.0",
        "graph_analyzer": "0.1.0",
        "geometry_resolver": "0.1.0",
        "feature_lowering": "0.1.0",
        "execution_planner": "0.1.0",
    }
)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Diagnostic message produced during compilation (spec 3.4.7, 6.7.3)."""

    stage: str
    code: ErrorCode
    pointer: str
    message: str
    severity: Literal["error", "warning"] = "error"
    module: str | None = None
    expected: tuple[str, ...] | None = None
    ref: str | None = None

    @classmethod
    def from_issue(
        cls,
        issue: ValidationIssue,
        stage: str,
        module: str | None = None,
    ) -> "Diagnostic":
        return cls(
            stage=stage,
            code=issue.code,
            pointer=issue.pointer,
            message=issue.message,
            severity=issue.severity,
            module=module,
            expected=issue.expected,
            ref=issue.ref,
        )

    def to_json(self) -> dict[str, JsonValue]:
        out: dict[str, JsonValue] = {
            "stage": self.stage,
            "code": self.code.value,
            "pointer": self.pointer,
            "message": self.message,
        }
        if self.severity != "error":
            out["severity"] = self.severity
        if self.module is not None:
            out["module"] = self.module
        if self.expected is not None:
            out["expected"] = list(self.expected)
        if self.ref is not None:
            out["ref"] = self.ref
        return out


@dataclass(frozen=True, slots=True)
class StageResult[T]:
    """Pure function result from a compiler stage (spec 6.7.1)."""

    output: T | None
    diagnostics: tuple[Diagnostic, ...] = ()
    needs: tuple[str, ...] = ()

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)


@dataclass(frozen=True, slots=True)
class CompileContext:
    """Context provided to compilation pipeline (spec 6.7.1)."""

    compiler_version: str
    profile: CapabilityProfile
    defaults: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class CompileInput:
    """Input to the compiler: pinned bundle manifest and stored documents (spec 6.7.1)."""

    manifest: BundleManifest
    documents: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class CompileResult:
    """Result of bundle compilation (spec 6.5.3, 6.7.3)."""

    plan: JsonValue | None
    plan_hash: str | None
    diagnostics: tuple[Diagnostic, ...]


# --- Stages implementing 6.7 stage contract ---


class ParserStage:
    """Stage 1 & 2: Parse stored bundle documents into PartGraph model (spec 6.7.2)."""

    version: Final[str] = STAGE_VERSIONS["parser"]

    @staticmethod
    def run(input_data: CompileInput, ctx: CompileContext) -> StageResult[PartGraph]:
        part_refs = [m for m in input_data.manifest.modules if m.module == "part"]
        if not part_refs:
            diag = Diagnostic(
                stage="parser",
                code=ErrorCode.IR_MODULE_MISSING,
                pointer="/modules",
                message="Bundle manifest contains no part module",
            )
            return StageResult(output=None, diagnostics=(diag,))

        part_ref = part_refs[0]
        ref_key = str(part_ref)
        if ref_key not in input_data.documents:
            diag = Diagnostic(
                stage="parser",
                code=ErrorCode.IR_MODULE_MISSING,
                pointer="/modules",
                message=f"Document for reference '{ref_key}' is missing",
                ref=ref_key,
            )
            return StageResult(output=None, diagnostics=(diag,))

        raw_doc = input_data.documents[ref_key]
        parsed = parse_part_graph(raw_doc)
        if isinstance(parsed, IssueReport):
            diags = tuple(
                Diagnostic.from_issue(issue, stage="parser", module="part")
                for issue in parsed.issues
            )
            return StageResult(output=None, diagnostics=diags)

        return StageResult(output=parsed)


class SemanticValidatorStage:
    """Stage 3: Validate PartGraph semantic rules (spec 5.7, 6.7.2)."""

    version: Final[str] = STAGE_VERSIONS["semantic_validator"]

    @staticmethod
    def run(graph: PartGraph, ctx: CompileContext) -> StageResult[PartGraph]:
        issues = validate_graph(graph)
        if issues:
            diags = tuple(
                Diagnostic.from_issue(issue, stage="semantic_validator", module="part")
                for issue in issues
            )
            has_error = any(d.severity == "error" for d in diags)
            return StageResult(output=None if has_error else graph, diagnostics=diags)
        return StageResult(output=graph)


class GraphAnalyzerStage:
    """Stage 4: Analyze graph dependencies and topological build order (spec 6.7.2)."""

    version: Final[str] = STAGE_VERSIONS["graph_analyzer"]

    @staticmethod
    def run(graph: PartGraph, ctx: CompileContext) -> StageResult[GraphAnalysis]:
        analysis = analyze_graph(graph)
        if analysis.cycle is not None:
            diags = tuple(
                Diagnostic(
                    stage="graph_analyzer",
                    code=ErrorCode.IR_CYCLE,
                    pointer=f"/nodes/{nid}/dependencies",
                    message=f"Dependency cycle involving node '{nid}'",
                    module="part",
                )
                for nid in analysis.cycle
            )
            return StageResult(output=None, diagnostics=diags)
        return StageResult(output=analysis)


class GeometryResolverStage:
    """Stage 5: Resolve geometry references and check standard planes (spec 6.7.2)."""

    version: Final[str] = STAGE_VERSIONS["geometry_resolver"]

    @staticmethod
    def run(graph: PartGraph, ctx: CompileContext) -> StageResult[PartGraph]:
        diags: list[Diagnostic] = []
        for node_id, node in graph.nodes.items():
            if isinstance(node, SketchNode) and node.plane not in STANDARD_PLANES:
                diags.append(
                    Diagnostic(
                        stage="geometry_resolver",
                        code=ErrorCode.COMPILE_UNSUPPORTED_FEATURE,
                        pointer=f"/nodes/{node_id}/plane",
                        message=f"Unsupported plane '{node.plane}'; standard planes required",
                        module="part",
                    )
                )
        if diags:
            return StageResult(output=None, diagnostics=tuple(diags))
        return StageResult(output=graph)


class FeatureLoweringStage:
    """Stage 6: Lower feature graph to backend operations (spec 6.5.2, 6.7.2)."""

    version: Final[str] = STAGE_VERSIONS["feature_lowering"]

    @staticmethod
    def run(
        input_pair: tuple[PartGraph, GraphAnalysis],
        ctx: CompileContext,
    ) -> StageResult[LoweringResult]:
        graph, analysis = input_pair
        lowered, issues = lower_graph(graph, analysis, ctx.profile, ctx.defaults)
        if issues:
            diags = tuple(
                Diagnostic.from_issue(issue, stage="feature_lowering", module="part")
                for issue in issues
            )
            return StageResult(output=None, diagnostics=diags)
        return StageResult(output=lowered)


class ExecutionPlannerStage:
    """Stage 7: Assemble Execution Plan and compute plan content hash (spec 6.5.3, 6.7.2)."""

    version: Final[str] = STAGE_VERSIONS["execution_planner"]

    @staticmethod
    def run(
        input_tuple: tuple[BundleManifest, LoweringResult],
        ctx: CompileContext,
    ) -> StageResult[tuple[dict[str, Any], str]]:
        manifest, lowering_result = input_tuple
        plan, plan_hash = build_plan(
            manifest=manifest,
            lowering_result=lowering_result,
            ctx=ctx,
            stage_versions=STAGE_VERSIONS,
        )
        return StageResult(output=(plan, plan_hash))


def compile_bundle(source: CompileInput, ctx: CompileContext) -> CompileResult:
    """Run compiler stages to produce an Execution Plan from an IR bundle (spec 6.7)."""
    p_res = ParserStage.run(source, ctx)
    if p_res.has_errors or p_res.output is None:
        return CompileResult(plan=None, plan_hash=None, diagnostics=p_res.diagnostics)

    graph = p_res.output
    for step_fn in (SemanticValidatorStage.run, GeometryResolverStage.run):
        step_res = step_fn(graph, ctx)
        if step_res.has_errors or step_res.output is None:
            return CompileResult(plan=None, plan_hash=None, diagnostics=step_res.diagnostics)

    a_res = GraphAnalyzerStage.run(graph, ctx)
    if a_res.has_errors or a_res.output is None:
        return CompileResult(plan=None, plan_hash=None, diagnostics=a_res.diagnostics)

    l_res = FeatureLoweringStage.run((graph, a_res.output), ctx)
    if l_res.has_errors or l_res.output is None:
        return CompileResult(plan=None, plan_hash=None, diagnostics=l_res.diagnostics)

    pl_res = ExecutionPlannerStage.run((source.manifest, l_res.output), ctx)
    if pl_res.has_errors or pl_res.output is None:
        return CompileResult(plan=None, plan_hash=None, diagnostics=pl_res.diagnostics)

    plan, plan_hash = pl_res.output
    return CompileResult(plan=plan, plan_hash=plan_hash, diagnostics=())


__all__ = [
    "STAGE_VERSIONS",
    "WORKING",
    "CompileContext",
    "CompileInput",
    "CompileResult",
    "Diagnostic",
    "ExecutionPlannerStage",
    "FeatureLoweringStage",
    "GeometryResolverStage",
    "GraphAnalyzerStage",
    "ParserStage",
    "SemanticValidatorStage",
    "StageResult",
    "build_order",
    "compile_bundle",
    "validate_graph",
]
