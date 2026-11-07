# Revolved Features (`BF-REV`, `CF-REV`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Revolved Boss/Base (`BF-REV-001`..`016`) and Revolved Cut (`CF-REV-001`..`006`) feature capabilities along with sketch centerline/construction line support (`SK-ENT-002`, `SK-ENT-003`) across the full vertical stack: IR schema, pure compiler validation & lowering, closed-form verification geometry, C# execution engine adapters, authoring guide/benchmark suite, and live SOLIDWORKS 2025 verification.

**Architecture:** A revolved feature (`revolve` or `cut_revolve`) creates or removes material by revolving a 2D planar profile around an axis of revolution (sketch centerline, coordinate axis, or cylindrical axis). The compiler validates the profile, angle, and axis, and lowers to an IPC `feature.create` operation. The verification engine computes closed-form volume and expected cylindrical faces using Pappus's Centroid Theorem. The C# adapter selects the profile sketch (Mark 0) and axis (Mark 4), invoking `IFeatureManager.FeatureRevolve2` with strict COM object tracking in `ComScope`.

**Tech Stack:** Python 3.13 (`cad-ir`, `cad-compiler`, `cad-verification`, `cad-application`), C# .NET Framework 4.8 (`ExecutionServer.Core`, `ExecutionServer.Adapters`), JSON Schema 2020-12, SOLIDWORKS 2025 Interop API (`IFeatureManager.FeatureRevolve2`, `ISketchManager.CreateCenterLine`).

**Spec:** [docs/architecture/part-feature-graph-ir.md](../../architecture/part-feature-graph-ir.md) §5.3, §5.7.3, [docs/specifications/ir-specification.md](../../specifications/ir-specification.md) §22.5.2, [docs/implementation/part-features/base-features.md](../../implementation/part-features/base-features.md) §`BF-REV`, [docs/implementation/part-features/cut-features.md](../../implementation/part-features/cut-features.md) §`CF-REV`, [docs/implementation/sketch/sketch-entities.md](../../implementation/sketch/sketch-entities.md) §`SK-ENT`.

## Global Constraints

- **Clean-room implementation (ADR-010):** Never copy code from SolidPilot or external repositories.
- **Pure Core Isolation (Guideline G2):** Pure core packages (`cad-ir`, `cad-compiler`, `cad-drawing`, `cad-geometry`, `cad-references`, `cad-verification`) perform zero I/O and have zero CAD vendor imports.
- **COM Lifecycle (Guideline G1):** Release temporary COM objects via `ComScope` / `Marshal.ReleaseComObject`. Never leak COM proxies across commands or out of the STA UI thread.
- **Schema-First Contracts (ADR-035):** Schemas in `schemas/` are single source of truth; never hand-edit generated models.
- **Drawings Frozen (ADR-057):** Do not modify `cad-drawing` or drawing pipelines.

## Review Focus

1. **Axis Resolution:** When `axis` is specified as a sketch centerline, coordinate axis (`axis:x`, `axis:y`, `axis:z`), or omitted (auto-detect sketch centerline), verify each case resolves deterministically or returns clean `IR_REFERENCE_UNRESOLVED`.
2. **Angle Bounds & Direction:** Angle must be in $(0, 360]$ degrees; test boundaries ($0^\circ$ rejected, $360^\circ$ full circle, mid-plane symmetry).
3. **Pappus Theorem Verification:** Verify closed-form volume matches mathematical expectation $V = \theta A \bar{r}$ for revolved cylindrical bushings and turned shafts.
4. **Revolved Cut Pre-conditions:** Cut revolve requires an existing solid body; verify semantic validator rejects orphan cut revolve without prior solid feature.
5. **Selection Marks in C#:** Mark 0 for sketch, Mark 4 for axis in `FeatureRevolve2`. Confirm no `SelectByID2` usage and zero COM leaks.

---

## File Structure

- **Schemas & Spec:**
  - `docs/adr/ADR-077-revolved-features.md`: Decision record for revolve semantics, axis resolution, and `FeatureRevolve2` parameters.
  - `schemas/part-feature-graph/features/revolve.json`: Revolve boss node schema.
  - `schemas/part-feature-graph/features/cut_revolve.json`: Revolve cut node schema.
  - `schemas/part-feature-graph/v0.json`: Node union update (add `revolve`, `cut_revolve`), add optional `construction: boolean` to `Line`.
  - `schemas/ipc/ops/sketch.create.json`: Add `construction` property to line entity.
  - `schemas/ipc/ops/feature.create.json`: Add `"revolve"`, `"cut_revolve"` to `type` enum; add revolution parameters (`axis`, `angle`, `mid_plane`, `reverse`, `thin`, `merge`).
- **Pure Core Python Packages:**
  - `packages/cad-ir/src/cad_ir/part_feature_graph/model.py`: `Revolve`, `CutRevolve` dataclasses; update `Line` with `construction: bool = False`.
  - `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`: Revolve and cut revolve parsing.
  - `packages/cad-compiler/src/cad_compiler/validator/semantic.py`: Revolve semantic validation (`_check_revolves`).
  - `packages/cad-compiler/src/cad_compiler/lowering/lower.py`: Lowering to `feature.create`.
  - `packages/cad-compiler/src/cad_compiler/registry.py` & `profile.py`: Revolve feature registration.
  - `packages/cad-verification/src/cad_verification/part.py`: Pappus centroid theorem volume and expected cylinder calculation for revolve and cut revolve.
- **Execution Server (C#):**
  - `apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs`: Support `construction` line creation via `sm.CreateCenterLine`.
  - `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs`: Revolve & Cut Revolve feature creation with Mark 0 (sketch) and Mark 4 (axis) via `FeatureRevolve2`.
  - `apps/execution-server/ExecutionServer.Tests/Parts/RevolveParamTests.cs`: Deserialization contract tests.
- **Application & Benchmarks:**
  - `packages/cad-application/src/cad_application/authoring_guide.py`: Revolve and cut revolve rules, centerline instructions, and shaft examples.
  - `packages/cad-application/src/cad_application/tools/list_feature_types.py`: Supported types update (`revolve`, `cut_revolve`).
  - `packages/cad-application/src/cad_application/authoring_eval/cases.py` & `references.py`: Eval case `turned_shaft` and `grooved_shaft`.
  - `tests/cad-benchmark/part_ir_baseline_answers.json`: Baseline answers.
- **Live Verification & Checklists:**
  - `tests/live/test_live_part_chain.py`: Live SOLIDWORKS 2025 integration tests (`test_live_revolve_shaft`, `test_live_revolve_cut_groove`).
  - `docs/implementation/part-features/base-features.md`, `cut-features.md`, `sketch/sketch-entities.md`: Checklist promotions.
  - `HANDOFF.md`: Handoff documentation update.

---

## Tasks

### Task 1: Spec & Schemas (ADR-077, Schemas, Spec v1.46)
- [ ] Create `docs/adr/ADR-077-revolved-features.md` documenting revolve boss and revolve cut semantics.
- [ ] Update `schemas/part-feature-graph/v0.json` (add `revolve` and `cut_revolve` references, add optional `construction: boolean` to `Line`).
- [ ] Create `schemas/part-feature-graph/features/revolve.json` and `cut_revolve.json`.
- [ ] Update `schemas/ipc/ops/sketch.create.json` (add `construction` to line entity).
- [ ] Update `schemas/ipc/ops/feature.create.json` (add `revolve`, `cut_revolve` and revolution parameters).
- [ ] Run `uv run python scripts/generate_contracts.py` to regenerate Python and C# models.
- [ ] Bump specification version to v1.46 across 35 topic docs, `docs/README.md`, `docs/specifications/README.md`, and `CHANGELOG.md`.
- [ ] Verify `uv run python scripts/generate_contracts.py --check` and `uv run pytest tests/contract/test_schema_fixtures.py` pass.

### Task 2: Pure Core IR & Compiler Lowering (`cad-ir` & `cad-compiler`)
- [ ] Write failing unit tests in `packages/cad-ir/tests/test_part_feature_graph.py` and `packages/cad-compiler/tests/test_compile.py`.
- [ ] Implement `Revolve` and `CutRevolve` dataclasses in `packages/cad-ir/src/cad_ir/part_feature_graph/model.py` and update `Line(construction=...)`.
- [ ] Implement parsing in `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`.
- [ ] Implement semantic validation in `packages/cad-compiler/src/cad_compiler/validator/semantic.py` (`_check_revolves`).
- [ ] Implement lowering in `packages/cad-compiler/src/cad_compiler/lowering/lower.py` (`_lower_revolve`).
- [ ] Register `revolve` and `cut_revolve` in `packages/cad-compiler/src/cad_compiler/registry.py` and `profile.py`.
- [ ] Update profile hashes / golden plan tests in `tests/fixtures/plans/`.
- [ ] Verify `uv run pytest packages/cad-ir packages/cad-compiler` passes and `uv run lint-imports` remains clean.

### Task 3: Verification Engine Geometry (`cad-verification`)
- [ ] Write failing test in `packages/cad-verification/tests/test_part.py` for revolve and cut revolve expected geometry.
- [ ] Implement `_apply_revolve` and `_apply_cut_revolve` in `packages/cad-verification/src/cad_verification/part.py`:
  - Calculate closed-form volume using Pappus's Centroid Theorem ($V = \theta A \bar{r}$).
  - Compute `ExpectedCylinder` for revolution faces.
  - Map native feature types `"Revolution"` and `"RevCut"`.
- [ ] Verify `uv run pytest packages/cad-verification` passes.

### Task 4: C# Execution Engine Adapters (`ExecutionServer.Core` & `ExecutionServer.Adapters`)
- [ ] Write tests in `apps/execution-server/ExecutionServer.Tests/Parts/RevolveParamTests.cs` validating `FeatureCreateParams` deserialization for `revolve` and `cut_revolve`.
- [ ] In `apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs`:
  - Handle `construction: true` on lines by calling `sm.CreateCenterLine`.
- [ ] In `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs`:
  - Implement `FeatureCreateParamsType.Revolve` and `CutRevolve`.
  - Select sketch with Mark 0 (`profileFeature.Select2(false, 0)`).
  - Select axis with Mark 4: centerline from sketch, or axis entity from coordinate/cylinder reference.
  - Call `doc.FeatureManager.FeatureRevolve2(...)`.
  - Track COM objects in `ComScope`.
- [ ] Verify `dotnet test apps/execution-server/ExecutionServer.Tests` passes and `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings/errors.

### Task 5: Authoring Guide & Benchmark Suite (`cad-application`)
- [ ] Update `authoring_guide.py` with `revolve` and `cut_revolve` syntax, rules, and turned shaft examples.
- [ ] Update `list_feature_types.py` to add `revolve` and `cut_revolve` to `MVP_TYPES`.
- [ ] Update `tests/contract/test_part_tools.py` (`EXPECTED_MVP_TYPES = 8`).
- [ ] Add `turned_shaft` and `grooved_shaft` to `cases.py`, `references.py`, and `part_ir_baseline_answers.json`.
- [ ] Verify `uv run python scripts/score_part_ir.py` passes all cases and `uv run pytest tests/cad-benchmark` passes.

### Task 6: Live SOLIDWORKS Verification & Promotion (`tests/live`, checklists)
- [ ] In `packages/cad-application/src/cad_application/jobs/plan_job.py`: verify `resolve_node_refs` handles revolve references.
- [ ] Add `test_live_revolve_shaft` and `test_live_revolve_cut_groove` in `tests/live/test_live_part_chain.py`.
- [ ] Run live verification against SOLIDWORKS 2025.
- [ ] Promote `BF-REV-001`, `BF-REV-002`, `BF-REV-005`, `BF-REV-007`, `BF-REV-008`, `BF-REV-009`, `BF-REV-010`, `BF-REV-014`, `BF-REV-015`, `BF-REV-016`, `CF-REV-001`, `CF-REV-002`, `CF-REV-003`, `CF-REV-004`, `SK-ENT-002`, `SK-ENT-003` to `Verified` in checklists.
- [ ] Audit checklists with `uv run python scripts/check_implementation_checklists.py --write`.
- [ ] Update `HANDOFF.md` with final state.
