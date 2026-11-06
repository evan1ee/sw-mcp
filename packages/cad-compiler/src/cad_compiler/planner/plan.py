"""Execution Planner: assembling the Execution Plan (spec 6.5.3, 6.7.2)."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from cad_ir.bundle.manifest import BundleManifest
from cad_ir.core.canonical import content_hash

from cad_compiler.lowering.lower import LoweringResult

if TYPE_CHECKING:
    from cad_compiler.api import CompileContext


def build_plan(
    manifest: BundleManifest,
    lowering_result: LoweringResult,
    ctx: "CompileContext",
    stage_versions: Mapping[str, str],
) -> tuple[dict[str, Any], str]:
    """Assemble the Execution Plan document and compute its content hash."""
    plan: dict[str, Any] = {
        "plan_schema_version": "0.1",
        "bundle": {
            "bundle_schema_version": manifest.bundle_schema_version,
            "modules": [str(m) for m in manifest.modules],
        },
        "provenance": {
            "compiler_version": ctx.compiler_version,
            "profile_hash": ctx.profile.hash,
            "stage_versions": dict(stage_versions),
        },
        "defaults": dict(ctx.defaults),
        "operations": lowering_result.operations,
        "verification_points": lowering_result.verification_points,
    }
    phash = content_hash(plan)
    return plan, phash
