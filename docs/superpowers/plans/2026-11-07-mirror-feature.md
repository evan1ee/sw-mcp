# Mirror Feature (`PAT-MIR`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Mirror Feature capability (`PAT-MIR-001` through `PAT-MIR-004`) across the full vertical stack: IR schema, pure compiler validation & lowering, closed-form verification geometry, C# execution engine adapters, authoring guide/benchmark suite, and live SOLIDWORKS 2025 verification.

**Architecture:** A mirror feature (`mirror`) reflects seed cut features across a symmetry plane (`plane:right`, `plane:top`, `plane:front`). The compiler lowers `mirror` to an IPC `feature.create` operation with type `mirror`, `seeds`, and `plane`. The verification engine calculates closed-form reflected geometry and expected cylinders. The C# adapter selects the mirror plane and seed features with appropriate selection marks in `FeatureAdapter.cs`, tracking COM objects in `ComScope`.

**Tech Stack:** Python 3.13 (`cad-ir`, `cad-compiler`, `cad-verification`, `cad-application`), C# .NET Framework 4.8 (`ExecutionServer.Core`, `ExecutionServer.Adapters`), JSON Schema 2020-12, SOLIDWORKS 2025 Interop API (`swFmMirrorPattern` / `InsertMirrorFeature2`).

**Spec:** [docs/architecture/part-feature-graph-ir.md](../../architecture/part-feature-graph-ir.md) §5.7.3, [docs/specifications/ir-specification.md](../../specifications/ir-specification.md) §22.5.2, [docs/implementation/part-features/patterns-mirrors.md](../../implementation/part-features/patterns-mirrors.md) §`PAT-MIR`.

## Global Constraints

- **Clean-room implementation (ADR-010):** Never copy code from SolidPilot or external repositories.
- **Pure Core Isolation (Guideline G2):** Pure core packages (`cad-ir`, `cad-compiler`, `cad-drawing`, `cad-geometry`, `cad-references`, `cad-verification`) perform zero I/O and have zero CAD vendor imports.
- **COM Lifecycle (Guideline G1):** Release temporary COM objects via `ComScope` / `Marshal.ReleaseComObject`. Never leak COM proxies across commands or out of the STA UI thread.
- **Schema-First Contracts (ADR-035):** Schemas in `schemas/` are single source of truth; never hand-edit generated models.
- **Drawings Frozen (ADR-057):** Do not modify `cad-drawing` or drawing pipelines.

---

## File Structure

- **Schemas & Spec:**
  - `docs/adr/ADR-076-mirror-feature.md`: Decision record for mirror feature semantics.
  - `schemas/part-feature-graph/features/mirror.json`: Mirror node schema.
  - `schemas/part-feature-graph/v0.json`: Node union update.
  - `schemas/ipc/ops/feature.create.json`: Feature creation operation schema update.
- **Pure Core Python Packages:**
  - `packages/cad-ir/src/cad_ir/part_feature_graph/model.py`: `Mirror` dataclass.
  - `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`: Mirror parsing.
  - `packages/cad-compiler/src/cad_compiler/validator/semantic.py`: Semantic validation.
  - `packages/cad-compiler/src/cad_compiler/lowering/lower.py`: Lowering to `feature.create`.
  - `packages/cad-compiler/src/cad_compiler/registry.py` & `profile.py`: Feature registration.
  - `packages/cad-verification/src/cad_verification/part.py`: Expected geometry reflection.
- **Execution Server (C#):**
  - `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs`: Mirror feature creation & plane selection.
  - `apps/execution-server/ExecutionServer.Tests/Parts/MirrorParamTests.cs`: Deserialization contract tests.
- **Application & Benchmarks:**
  - `packages/cad-application/src/cad_application/authoring_guide.py`: Rules & example.
  - `packages/cad-application/src/cad_application/tools/list_feature_types.py`: Supported types update.
  - `packages/cad-application/src/cad_application/authoring_eval/cases.py` & `references.py`: Eval case `plate_mirror_hole`.
  - `tests/cad-benchmark/part_ir_baseline_answers.json`: Baseline answer.
- **Live Verification & Checklists:**
  - `tests/live/test_live_part_chain.py`: Live SOLIDWORKS 2025 integration tests.
  - `docs/implementation/part-features/patterns-mirrors.md`: Checklist promotion (`PAT-MIR-001`..`004`).
  - `HANDOFF.md`: Handoff documentation update.

---

## Tasks

### Task 1: Spec & Schemas (ADR-076, Schemas, Spec v1.45)
- [ ] Create `docs/adr/ADR-076-mirror-feature.md` documenting mirror feature semantics.
- [ ] Create `schemas/part-feature-graph/features/mirror.json` defining `seeds` and `plane`.
- [ ] Update `schemas/part-feature-graph/v0.json` with `mirror` node.
- [ ] Update `schemas/ipc/ops/feature.create.json` with `mirror` type.
- [ ] Run `python scripts/generate_contracts.py` to regenerate Python and C# models.
- [ ] Bump specification version to v1.45 across 35 topic docs, `docs/README.md`, `docs/specifications/README.md`, and `CHANGELOG.md`.
- [ ] Verify `python scripts/generate_contracts.py --check` and `pytest tests/contract/test_schema_fixtures.py` pass.

### Task 2: Pure Core IR & Compiler Lowering (`cad-ir` & `cad-compiler`)
- [ ] Write failing unit tests in `packages/cad-ir/tests/test_part_feature_graph.py` and `packages/cad-compiler/tests/test_compile.py`.
- [ ] Implement `Mirror` dataclass in `packages/cad-ir/src/cad_ir/part_feature_graph/model.py` and export in `__init__.py`.
- [ ] Implement parsing in `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`.
- [ ] Implement semantic validation in `packages/cad-compiler/src/cad_compiler/validator/semantic.py` (`_check_mirrors`).
- [ ] Implement lowering in `packages/cad-compiler/src/cad_compiler/lowering/lower.py` (`_lower_mirror`).
- [ ] Register `mirror` in `packages/cad-compiler/src/cad_compiler/registry.py` and `profile.py`.
- [ ] Verify `pytest packages/cad-ir packages/cad-compiler` passes and `lint-imports` remains clean.

### Task 3: Verification Engine Geometry (`cad-verification`)
- [ ] Write failing test in `packages/cad-verification/tests/test_part.py` for mirror expected geometry.
- [ ] Implement `_apply_mirror_instances` in `packages/cad-verification/src/cad_verification/part.py`:
  - Calculate reflected coordinates across `plane:front`, `plane:top`, or `plane:right`.
  - Reflect cylinder positions and axes.
  - Subtract mirrored cut volume and reflect moments.
  - Set native feature type `"MirrorPattern"`.
- [ ] Verify `pytest packages/cad-verification` passes.

### Task 4: C# Execution Engine Adapters (`ExecutionServer.Core` & `ExecutionServer.Adapters`)
- [ ] Write tests in `apps/execution-server/ExecutionServer.Tests/Parts/MirrorParamTests.cs` validating `FeatureCreateParams` deserialization for `mirror`.
- [ ] In `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs`:
  - Implement `FeatureCreateParamsType.Mirror` handling.
  - Implement `ResolveMirrorPlaneEntity` / plane selection (Mark 2 for plane, Mark 1 for seeds).
  - Use `doc.FeatureManager.InsertMirrorFeature2` or `CreateDefinition(swFmMirrorPattern)` / `CreateFeature`.
  - Track COM objects in `ComScope`.
- [ ] Verify `dotnet test apps/execution-server/ExecutionServer.Tests` passes and `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings/errors.

### Task 5: Authoring Guide & Benchmark Suite (`cad-application`)
- [ ] Update `authoring_guide.py` with `mirror` syntax, rules, and example.
- [ ] Update `list_feature_types.py` to add `mirror`.
- [ ] Update `tests/contract/test_part_tools.py` (`EXPECTED_MVP_TYPES = 6`).
- [ ] Add `plate_mirror_hole` to `cases.py`, `references.py`, and `part_ir_baseline_answers.json`.
- [ ] Verify `score_part_ir.py` passes `18/18` and `test_part_ir_benchmark.py` passes.

### Task 6: Live SOLIDWORKS Verification & Promotion (`tests/live`, checklists)
- [ ] In `packages/cad-application/src/cad_application/jobs/plan_job.py`: verify `resolve_node_refs` handles mirror references.
- [ ] Add `test_live_mirror_plate` and `test_live_direct_mirror_ops` in `tests/live/test_live_part_chain.py`.
- [ ] Run live verification against SOLIDWORKS 2025.
- [ ] Promote `PAT-MIR-001` through `PAT-MIR-004` to `Verified` in `docs/implementation/part-features/patterns-mirrors.md`.
- [ ] Run `python scripts/check_implementation_checklists.py --write`.
- [ ] Run complete verification suite and update `HANDOFF.md`.
