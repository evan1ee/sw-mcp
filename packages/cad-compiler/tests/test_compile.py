"""Tests for compilation to Execution Plan (spec 6.5.3, 6.7)."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Final, cast

import pytest
from cad_compiler.api import (
    WORKING,
    CompileContext,
    CompileInput,
    Diagnostic,
    ExecutionPlannerStage,
    FeatureLoweringStage,
    GeometryResolverStage,
    GraphAnalyzerStage,
    ParserStage,
    SemanticValidatorStage,
    StageResult,
    compile_bundle,
)
from cad_compiler.profile import CapabilityProfile
from cad_ir.bundle.manifest import BundleManifest
from cad_ir.core.refs import parse_document_ref
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated import ErrorCode
from cad_ir.generated.ipc import HelloResult, OperationInfo, SolidWorksInfo

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas" / "part-feature-graph" / "valid"
PLATE_FIXTURE = FIXTURE_DIR / "plate_4h.json"
GOLDEN_PLAN = ROOT / "tests" / "fixtures" / "plans" / "plate_4h.json"
PLAN_SCHEMA_ID = "https://sw-mcp.invalid/schemas/execution-plan/v0.json"
SKETCH_CREATE_ID = "https://sw-mcp.invalid/schemas/ipc/ops/sketch.create.json"
FEATURE_CREATE_ID = "https://sw-mcp.invalid/schemas/ipc/ops/feature.create.json"
DIM_2D: Final[int] = 2


def _make_session(
    operations: tuple[str, ...] = ("part.create", "sketch.create", "feature.create"),
) -> HelloResult:
    return HelloResult(
        protocol="0.1",
        addin_version="0.1.0",
        solidworks=SolidWorksInfo(
            version="2025",
            service_pack="sp1",
            ui_language="en-US",
        ),
        capabilities=(),
        operations=tuple(OperationInfo(op=op, schema_version="0.1") for op in operations),
        licensed_modules=(),
        warnings=(),
    )


def _plate_input(revision: int = 1) -> tuple[CompileInput, CompileContext]:
    raw: dict[str, Any] = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
    ref_str = f"part:plate_4h@{revision}"
    manifest = BundleManifest(
        bundle_schema_version="1.0",
        modules=(parse_document_ref(ref_str),),
    )
    source = CompileInput(
        manifest=manifest,
        documents={ref_str: raw},
    )
    profile = CapabilityProfile.from_session(_make_session())
    ctx = CompileContext(
        compiler_version="0.1.0",
        profile=profile,
        defaults={},
    )
    return source, ctx


def test_plan_matches_golden() -> None:
    source, ctx = _plate_input(revision=1)
    result = compile_bundle(source, ctx)
    assert result.diagnostics == ()
    assert result.plan is not None
    plan = cast(dict[str, Any], result.plan)

    ops_dict = cast(dict[str, Any], plan["operations"])
    sorted_ops: list[dict[str, Any]] = sorted(
        [cast(dict[str, Any], o) for o in ops_dict.values()],
        key=lambda o: int(cast(int, o["sequence"])),
    )
    op_names = [o["op"] for o in sorted_ops]
    assert op_names == [
        "part.create",
        "sketch.create",
        "feature.create",
        "sketch.create",
        "feature.create",
    ]

    for op in sorted_ops:
        assert op["document"] == WORKING

    extrude_op = sorted_ops[2]
    extrude_params = cast(dict[str, Any], extrude_op["params"])
    assert extrude_params["profile"] == "sketch_base"
    cut_op = sorted_ops[4]
    cut_params = cast(dict[str, Any], cut_op["params"])
    assert cut_params["profile"] == "sketch_holes"

    sketch1_op = sorted_ops[1]
    sketch1_params = cast(dict[str, Any], sketch1_op["params"])
    sketch1_entities = cast(list[dict[str, Any]], sketch1_params["entities"])
    for ent in sketch1_entities:
        assert len(cast(list[float], ent["start"])) == DIM_2D
        assert len(cast(list[float], ent["end"])) == DIM_2D
    sketch2_op = sorted_ops[3]
    sketch2_params = cast(dict[str, Any], sketch2_op["params"])
    sketch2_entities = cast(list[dict[str, Any]], sketch2_params["entities"])
    for ent in sketch2_entities:
        assert len(cast(list[float], ent["center"])) == DIM_2D

    sk1_issues = list(
        validate_against_schema(sketch1_op["params"], f"{SKETCH_CREATE_ID}#/$defs/Params")
    )
    assert sk1_issues == []
    ext_issues = list(
        validate_against_schema(extrude_op["params"], f"{FEATURE_CREATE_ID}#/$defs/Params")
    )
    assert ext_issues == []
    sk2_issues = list(
        validate_against_schema(sketch2_op["params"], f"{SKETCH_CREATE_ID}#/$defs/Params")
    )
    assert sk2_issues == []
    cut_issues = list(
        validate_against_schema(cut_op["params"], f"{FEATURE_CREATE_ID}#/$defs/Params")
    )
    assert cut_issues == []

    assert plan["verification_points"] == ["op_3", "op_5"]

    golden = json.loads(GOLDEN_PLAN.read_text(encoding="utf-8"))
    assert plan == golden


def test_plan_validates_against_schema() -> None:
    source, ctx = _plate_input(revision=1)
    result = compile_bundle(source, ctx)
    assert result.plan is not None
    issues = list(validate_against_schema(result.plan, PLAN_SCHEMA_ID))
    assert issues == []


def test_revision_changes_plan_hash_but_not_operations() -> None:
    """A plan records the revision it was built from, so the hash differs (spec 6.7.4)."""
    source1, ctx1 = _plate_input(revision=1)
    source2, ctx2 = _plate_input(revision=2)
    res1 = compile_bundle(source1, ctx1)
    res2 = compile_bundle(source2, ctx2)
    assert res1.plan is not None
    assert res2.plan is not None
    plan1 = cast(dict[str, Any], res1.plan)
    plan2 = cast(dict[str, Any], res2.plan)
    assert plan1["operations"] == plan2["operations"]
    assert plan1["bundle"] != plan2["bundle"]
    assert res1.plan_hash != res2.plan_hash


def test_determinism() -> None:
    source, ctx = _plate_input(revision=1)
    res1 = compile_bundle(source, ctx)
    res2 = compile_bundle(source, ctx)
    assert res1.plan_hash == res2.plan_hash

    script = f"""
import json
from pathlib import Path
from cad_compiler.api import CompileInput, CompileContext, compile_bundle
from cad_compiler.profile import CapabilityProfile
from cad_ir.bundle.manifest import BundleManifest
from cad_ir.core.refs import parse_document_ref
from cad_ir.generated.ipc import HelloResult, OperationInfo, SolidWorksInfo

plate_fixture = Path(r"{PLATE_FIXTURE}")
raw = json.loads(plate_fixture.read_text(encoding="utf-8"))
ref_str = "part:plate_4h@1"
manifest = BundleManifest("1.0", (parse_document_ref(ref_str),))
source = CompileInput(manifest=manifest, documents={{ref_str: raw}})
session = HelloResult(
    protocol="0.1",
    addin_version="0.1.0",
    solidworks=SolidWorksInfo(version="2025", service_pack="sp1", ui_language="en-US"),
    capabilities=(),
    operations=(
        OperationInfo(op="part.create", schema_version="0.1"),
        OperationInfo(op="sketch.create", schema_version="0.1"),
        OperationInfo(op="feature.create", schema_version="0.1"),
    ),
    licensed_modules=(),
    warnings=(),
)
ctx = CompileContext("0.1.0", CapabilityProfile.from_session(session), {{}})
res = compile_bundle(source, ctx)
print(res.plan_hash)
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(ROOT),
    )
    sub_hash = proc.stdout.strip()
    assert sub_hash == res1.plan_hash


def test_unsupported_plane() -> None:
    raw: dict[str, Any] = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
    raw["nodes"]["sketch_base"]["plane"] = "datum:A"
    raw["nodes"]["sketch_holes"]["plane"] = "datum:A"
    ref_str = "part:plate_4h@1"
    manifest = BundleManifest("1.0", (parse_document_ref(ref_str),))
    source = CompileInput(manifest=manifest, documents={ref_str: raw})
    profile = CapabilityProfile.from_session(_make_session())
    ctx = CompileContext("0.1.0", profile, {})
    result = compile_bundle(source, ctx)
    assert result.plan is None
    assert any(d.code == ErrorCode.COMPILE_UNSUPPORTED_FEATURE for d in result.diagnostics)


def test_missing_operation() -> None:
    session = _make_session(operations=("part.create", "sketch.create"))
    profile = CapabilityProfile.from_session(session)
    source, _ = _plate_input(revision=1)
    ctx = CompileContext("0.1.0", profile, {})
    result = compile_bundle(source, ctx)
    assert result.plan is None
    assert any(d.code == ErrorCode.BACKEND_CAPABILITY_MISSING for d in result.diagnostics)


def _multi_module_input(refs: tuple[str, ...]) -> CompileInput:
    raw: dict[str, Any] = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
    return CompileInput(
        manifest=BundleManifest(
            bundle_schema_version="1.0",
            modules=tuple(parse_document_ref(ref) for ref in refs),
        ),
        documents={ref: raw for ref in refs},
    )


@pytest.mark.parametrize(
    "refs",
    [
        pytest.param(("part:plate_4h@1", "part:other@1", "assembly:a@1"), id="two_parts"),
        pytest.param(("part:plate_4h@1", "assembly:a@1"), id="part_and_assembly"),
    ],
)
def test_bundle_beyond_one_part_is_refused(refs: tuple[str, ...]) -> None:
    """Nothing in a bundle is dropped silently (5.3.6): assemblies do not compile yet."""
    _, ctx = _plate_input(revision=1)
    result = compile_bundle(_multi_module_input(refs), ctx)
    assert result.plan is None
    assert result.plan_hash is None
    assert [d.code for d in result.diagnostics] == [ErrorCode.COMPILE_UNSUPPORTED_FEATURE]
    assert result.diagnostics[0].pointer == "/modules"


def test_compile_preserves_warning_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    source, ctx = _plate_input(revision=1)
    orig_validate = SemanticValidatorStage.run

    def mock_run(graph: Any, ctx: Any) -> Any:
        res = orig_validate(graph, ctx)
        warning = Diagnostic(
            stage="semantic_validator",
            code=ErrorCode.IR_RULE_VIOLATED,
            pointer="/test",
            message="Test non-fatal warning",
            severity="warning",
        )
        return StageResult(output=res.output, diagnostics=(warning,))

    monkeypatch.setattr(SemanticValidatorStage, "run", mock_run)
    result = compile_bundle(source, ctx)
    assert result.plan is not None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].severity == "warning"
    assert result.diagnostics[0].message == "Test non-fatal warning"


def test_stage_execution_order_and_propagation(monkeypatch: pytest.MonkeyPatch) -> None:
    called_stages: list[str] = []

    orig_p = ParserStage.run
    orig_v = SemanticValidatorStage.run
    orig_a = GraphAnalyzerStage.run
    orig_g = GeometryResolverStage.run
    orig_l = FeatureLoweringStage.run
    orig_pl = ExecutionPlannerStage.run

    def mock_p(inp: Any, ctx: Any) -> Any:
        called_stages.append("parser")
        return orig_p(inp, ctx)

    def mock_v(inp: Any, ctx: Any) -> Any:
        called_stages.append("semantic_validator")
        return orig_v(inp, ctx)

    def mock_a(inp: Any, ctx: Any) -> Any:
        called_stages.append("graph_analyzer")
        return orig_a(inp, ctx)

    def mock_g(inp: Any, ctx: Any) -> Any:
        called_stages.append("geometry_resolver")
        return orig_g(inp, ctx)

    def mock_l(inp: Any, ctx: Any) -> Any:
        called_stages.append("feature_lowering")
        return orig_l(inp, ctx)

    def mock_pl(inp: Any, ctx: Any) -> Any:
        called_stages.append("execution_planner")
        return orig_pl(inp, ctx)

    monkeypatch.setattr(ParserStage, "run", mock_p)
    monkeypatch.setattr(SemanticValidatorStage, "run", mock_v)
    monkeypatch.setattr(GraphAnalyzerStage, "run", mock_a)
    monkeypatch.setattr(GeometryResolverStage, "run", mock_g)
    monkeypatch.setattr(FeatureLoweringStage, "run", mock_l)
    monkeypatch.setattr(ExecutionPlannerStage, "run", mock_pl)

    source, ctx = _plate_input(revision=1)
    res = compile_bundle(source, ctx)
    assert res.plan is not None
    assert called_stages == [
        "parser",
        "semantic_validator",
        "graph_analyzer",
        "geometry_resolver",
        "feature_lowering",
        "execution_planner",
    ]
