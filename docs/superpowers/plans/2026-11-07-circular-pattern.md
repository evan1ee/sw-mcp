# Circular Feature Pattern (`PAT-CIR`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Circular Feature Pattern (`PAT-CIR-001` through `PAT-CIR-005`) across all layers of `sw-mcp`, bump spec to v1.44, create ADR-075, support in authoring guide & benchmark (17/17), and verify live in SOLIDWORKS 2025.

**Architecture:** Extend Part Feature Graph IR with a dedicated `circular_pattern` node, lower it via `cad-compiler` to a typed `feature.create` IPC operation, model expected mass properties in `cad-verification`, execute natively in C# `FeatureAdapter` via `swFmCirPattern` (`ICircularPatternFeatureData`) with COM cleanup, and verify end-to-end live.

**Tech Stack:** Python 3.13, Pydantic/dataclasses, JSON Schema 2020-12, .NET 4.8 / C# 10, SOLIDWORKS 2025 API, pytest, dotnet test.

**Spec:** [`docs/architecture/feature-schema-guide.md`](file:///d:/01_Data/code/sw-mcp/docs/architecture/feature-schema-guide.md) §5.7.3, [`docs/specifications/ir-specification.md`](file:///d:/01_Data/code/sw-mcp/docs/specifications/ir-specification.md) §22.5.2, [`docs/specifications/solidworks-adapter.md`](file:///d:/01_Data/code/sw-mcp/docs/specifications/solidworks-adapter.md) §8.9.11, [`docs/implementation/part-features/patterns-mirrors.md`](file:///d:/01_Data/code/sw-mcp/docs/implementation/part-features/patterns-mirrors.md).

## Global Constraints

- Clean-room implementation: never copy code from reference implementation SolidPilot (ADR-010).
- Schema-first contracts: `schemas/` is the single source of truth; never hand-edit generated code (ADR-035).
- Pure core isolation: `cad-ir`, `cad-compiler`, and `cad-verification` must have zero I/O, zero network/clock dependencies, and zero CAD imports (Guideline G2).
- C# COM safety: wrap entity selection and feature data objects in `ComScope` / `try-finally` with `Marshal.ReleaseComObject`; never release root doc or app objects (Guideline G1).
- CAD-free ExecutionServer.Core: banned symbols analyzer rules strictly enforced (ADR-038).
- 2D drawings remain frozen per ADR-057.
- No completion claims without fresh verification output.

## Review Focus

1. **Axis reference resolution:** When `axis` is specified as a standard plane (e.g. `"plane:front"`), the rotation axis is the normal through origin (Z-axis). If a solid body has a cylindrical face or circular edge coaxial with that axis, it must be located and selected without COM leaks.
2. **Angular units:** SOLIDWORKS API `ICircularPatternFeatureData.Spacing` requires radians, while IR and IPC contracts specify degrees. Conversions must be deterministic and quantized.
3. **Equal spacing semantics:** When `equal_spacing: true`, `spacing` represents the total angle (typically 360°); when `false`, `spacing` is the incremental step angle.
4. **Pre-selection marks:** SOLIDWORKS `CreateDefinition(swFmCirPattern)` requires seed features marked with Mark 4 and axis marked with Mark 1 before creating definition.
5. **Node ID resolution:** Like linear pattern, `seeds` and `axis` in `plan_job.py` must resolve IR node names to native feature handles before sending `feature.create` to the add-in.

---

### Task 1: Spec & Schemas (ADR-075, Schemas, Spec v1.44)

**Files:**
- Create: `docs/adr/ADR-075-circular-pattern-feature.md`
- Create: `schemas/part-feature-graph/features/circular_pattern.json`
- Modify: `schemas/part-feature-graph/v0.json`
- Modify: `schemas/ipc/ops/feature.create.json`
- Modify: `docs/specifications/README.md`
- Modify: `docs/specifications/CHANGELOG.md`
- Modify: all 35 doc topic file headers (spec v1.44)
- Test: `tests/contract/test_schema_fixtures.py`, `tests/contract/test_generated_contracts.py`

- [ ] Write ADR-075 in `docs/adr/ADR-075-circular-pattern-feature.md` defining circular pattern feature, parameters (`seeds`, `axis`, `count`, `spacing`, `equal_spacing`, `reverse`), API mapping, and COM lifecycle rules.
- [ ] Create `schemas/part-feature-graph/features/circular_pattern.json` with JSON Schema 2020-12 validation.
- [ ] Update `schemas/part-feature-graph/v0.json` to include `$defs/CircularPattern` and reference in node union.
- [ ] Update `schemas/ipc/ops/feature.create.json` adding `"circular_pattern"` to `type` enum and adding circular pattern properties (`axis`, `count`, `spacing`, `equal_spacing`, `reverse`).
- [ ] Add schema fixtures in `tests/fixtures/schemas/` for valid/invalid circular pattern payloads.
- [ ] Regenerate contracts via `uv run python scripts/generate_contracts.py`.
- [ ] Bump spec version to v1.44 across documentation files and document in `CHANGELOG.md`.
- [ ] Verify `uv run python scripts/generate_contracts.py --check` and `uv run pytest tests/contract/test_schema_fixtures.py` pass.
- [ ] Commit: `spec: define circular pattern feature in IR and IPC schemas (spec v1.44, ADR-075)`.

### Task 2: Pure Core IR & Compiler Lowering (`cad-ir` & `cad-compiler`)

**Files:**
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/model.py`
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`
- Modify: `packages/cad-compiler/src/cad_compiler/validator/semantic.py`
- Modify: `packages/cad-compiler/src/cad_compiler/lowering/lower.py`
- Modify: `packages/cad-compiler/src/cad_compiler/registry.py`
- Test: `packages/cad-ir/tests/test_part_feature_graph.py`, `packages/cad-compiler/tests/test_rules.py`, `packages/cad-compiler/tests/test_compile.py`

- [ ] Write failing unit tests for `CircularPattern` IR parsing and semantic validation (seed existence, axis format, count >= 2, spacing in (0, 360], dependency on base and seeds).
- [ ] Implement `CircularPattern` dataclass in `cad_ir.part_feature_graph.model` and parser in `parse.py`.
- [ ] Implement semantic rules in `cad_compiler.validator.semantic` validating circular pattern integrity.
- [ ] Implement lowering in `cad_compiler.lowering.lower` producing `feature.create` operation for circular pattern.
- [ ] Register `circular_pattern` in `cad_compiler.registry`.
- [ ] Verify pure core unit tests pass: `uv run pytest packages/cad-ir packages/cad-compiler`.
- [ ] Commit: `feat(compiler): support circular pattern feature in IR and compiler lowering`.

### Task 3: Verification Engine Geometry (`cad-verification`)

**Files:**
- Modify: `packages/cad-verification/src/cad_verification/part.py`
- Modify: `packages/cad-verification/src/cad_verification/api/contracts.py`
- Test: `packages/cad-verification/tests/test_part.py`

- [ ] Write failing tests for closed-form expected geometry of parts with circular patterns.
- [ ] Implement expected geometry calculations in `cad_verification.part`:
  - Total instances = `count`.
  - Replicated seed volume: $V = V_{\text{base}} - \text{count} \times V_{\text{seed\_cut}}$.
  - Cylinder contracts: replicate seed cylinders across `count` instances around the axis.
  - Native feature type: `"CirPattern"`.
- [ ] Update contract verification in `contracts.py` to recognize `"CirPattern"`.
- [ ] Verify `cad-verification` tests pass: `uv run pytest packages/cad-verification`.
- [ ] Commit: `feat(verification): compute expected volume, surface area, and cylinders for circular patterns`.

### Task 4: C# Execution Engine Adapters (`ExecutionServer.Adapters`)

**Files:**
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs`
- Create: `apps/execution-server/ExecutionServer.Tests/Parts/CircularPatternParamTests.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/Parts/CircularPatternParamTests.cs`

- [ ] Write deserialization and parameter validation tests in `CircularPatternParamTests.cs`.
- [ ] In `FeatureAdapter.cs`, implement `FeatureCreateParamsType.CircularPattern`:
  - Pre-select seed features with Mark 4.
  - Resolve rotational axis entity (cylindrical face or circular edge matching axis direction) with Mark 1.
  - Call `doc.FeatureManager.CreateDefinition((int)swFeatureNameID_e.swFmCirPattern)`.
  - Populate `TotalInstances`, `Spacing` (converted to radians), `EqualSpacing`, `ReverseDirection`.
  - Call `CreateFeature(featData)` with COM tracking via `ComScope`.
- [ ] Verify `dotnet test apps/execution-server/ExecutionServer.Tests` passes and `dotnet build` succeeds in both Debug and Release.
- [ ] Commit: `feat(execution): implement circular pattern creation in FeatureAdapter`.

### Task 5: Authoring Guide & Benchmark Suite (`cad-application` & `tests/cad-benchmark`)

**Files:**
- Modify: `packages/cad-application/src/cad_application/authoring_guide.py`
- Modify: `packages/cad-application/src/cad_application/tools/list_feature_types.py`
- Modify: `packages/cad-application/src/cad_application/authoring_eval/cases.py`
- Modify: `packages/cad-application/src/cad_application/authoring_eval/references.py`
- Modify: `tests/cad-benchmark/part_ir_baseline_answers.json`
- Test: `tests/contract/test_part_tools.py`, `tests/cad-benchmark/test_part_ir_benchmark.py`

- [ ] Add `circular_pattern` to `authoring_guide.py` rules, schema definitions, and worked examples (round flange with 6 bolt holes).
- [ ] Add `circular_pattern` to `list_feature_types.py`.
- [ ] Add `round_flange_pattern_holes` case and reference IR in `cases.py` and `references.py`.
- [ ] Update `tests/cad-benchmark/part_ir_baseline_answers.json` with the new fixture.
- [ ] Run benchmark evaluation via `uv run python scripts/score_part_ir.py` ensuring 17/17 cases pass.
- [ ] Verify `uv run pytest tests/contract/test_part_tools.py` passes (with `EXPECTED_MVP_TYPES = 5`).
- [ ] Commit: `feat(eval): add circular pattern to authoring guide and benchmark suite (17/17)`.

### Task 6: Live SOLIDWORKS Verification & Promotion (`tests/live`, checklists)

**Files:**
- Modify: `packages/cad-application/src/cad_application/jobs/plan_job.py`
- Modify: `tests/live/test_live_part_chain.py`
- Modify: `docs/implementation/part-features/patterns-mirrors.md`
- Modify: `docs/implementation/README.md`
- Modify: `HANDOFF.md`
- Test: `tests/live/test_live_part_chain.py`

- [ ] Update `plan_job.py` `resolve_node_refs` to resolve `axis` if it points to a feature node.
- [ ] Add `test_live_circular_pattern_flange` and `test_live_direct_circular_pattern_ops` in `tests/live/test_live_part_chain.py`.
- [ ] Run live tests against SOLIDWORKS 2025 and verify clean execution and volume match.
- [ ] Promote `PAT-CIR-001`, `PAT-CIR-002`, `PAT-CIR-003`, `PAT-CIR-004`, `PAT-CIR-005` to `Verified` in `patterns-mirrors.md`.
- [ ] Run `uv run python scripts/check_implementation_checklists.py --write` to update `docs/implementation/README.md`.
- [ ] Run complete verification suite (`generate_contracts.py --check`, `ruff`, `pyright`, `lint-imports`, `pytest`, `dotnet test`).
- [ ] Update `HANDOFF.md` with updated verified counts and test baselines.
- [ ] Commit: `feat(live): verify circular pattern on live SOLIDWORKS and promote to verified`.
