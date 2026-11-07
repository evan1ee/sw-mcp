# Linear Pattern Feature (`PAT-LIN`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Linear Feature Pattern (`PAT-LIN-001` through `PAT-LIN-004`) end-to-end across spec/schemas (v1.43, ADR-074), pure-core IR & compiler lowering, verification geometry, C# add-in adapters (`ILinearPatternFeatureData`), authoring guide/benchmark, and live SOLIDWORKS 2025 verification.

**Architecture:** Pure-core / port-adapter / STA add-in layering (Guideline G1, G2, ADR-010, ADR-035, ADR-038, ADR-059, ADR-068, ADR-074). Define schema contracts for `linear_pattern` (`seeds`, `direction_1`, `direction_2`). Compile to `feature.create` operations. Execute in `FeatureAdapter.cs` using `FeatureManager.CreateDefinition(swFmLPattern)` and `ILinearPatternFeatureData` with Guideline G1 COM release. Verify expected closed-form mass properties and cylinders in `cad-verification`.

**Tech Stack:** Python 3.13 (`cad-ir`, `cad-compiler`, `cad-verification`, `cad-application`, `core-service`), C# / .NET Framework 4.8 (`ExecutionServer.Core`, `ExecutionServer.Adapters`, `ExecutionServer.AddIn`), JSON Schema Draft 2020-12, SOLIDWORKS 2025 COM Interop.

**Spec:** [`docs/architecture/feature-schema-guide.md`](file:///d:/01_Data/code/sw-mcp/docs/architecture/feature-schema-guide.md) §5.7.3, [`docs/specifications/ir-specification.md`](file:///d:/01_Data/code/sw-mcp/docs/specifications/ir-specification.md) §22.5.2, [`docs/specifications/solidworks-adapter.md`](file:///d:/01_Data/code/sw-mcp/docs/specifications/solidworks-adapter.md) §8.9.11, [`docs/implementation/part-features/patterns-mirrors.md`](file:///d:/01_Data/code/sw-mcp/docs/implementation/part-features/patterns-mirrors.md).

## Global Constraints

- **Clean-room implementation (ADR-010):** Do not inspect or copy code from reference implementation; follow observable behavior, contracts, and failure modes only.
- **Custody of source files (ADR-022):** Never write to source parts or run SOLIDWORKS macros.
- **Schema-first contracts (ADR-035):** Edit `schemas/`; regenerate Python and C# types via `scripts/generate_contracts.py`. Never hand-edit generated files.
- **Layering & Purity (Guideline G2):** Core packages (`cad-ir`, `cad-compiler`, `cad-verification`) must have zero I/O, zero network/clock dependencies, and zero CAD vendor imports.
- **C# COM object safety (Guideline G1, ADR-059):** Track and release temporary COM objects in `ComScope` / `try...finally` with `Marshal.ReleaseComObject`. Never release root application or document objects.
- **CAD-free ExecutionServer.Core (ADR-038):** No SOLIDWORKS references in `ExecutionServer.Core` or `ExecutionServer.Tests`.
- **2D Drawing freeze (ADR-057):** Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark`.

## Review Focus

1. **Seed Feature Binding:** Pattern seeds must resolve to valid, unsuppressed cut features that depend on the base body.
2. **Direction Resolution:** Directions must support standard planes (`plane:right` for X, `plane:top` for Y) as well as axis references.
3. **Instance Bounds:** Compiler and validator must ensure all patterned instances lie strictly within the base extrude profile.
4. **Closed-Form Geometry:** Verification engine must multiply seed volume by total instances $N$ ($D_1 \text{ count} \times (D_2 \text{ count or } 1)$) and replicate cylinder count.
5. **COM Lifecycle in Adapter:** When populating `PatternFeatureArray` and `D1Axis`, ensure all temporary COM pointers are tracked and released.

---

### Task 1: Spec & Schemas (`schemas/`, docs bump to v1.43, ADR-074)

**Files:**
- Create: `docs/adr/ADR-074-linear-pattern-feature.md`
- Create: `schemas/part-feature-graph/features/linear_pattern.json`
- Modify: `schemas/part-feature-graph/v0.json`
- Modify: `schemas/ipc/ops/feature.create.json`
- Modify: `docs/architecture/feature-schema-guide.md`
- Modify: `docs/specifications/ir-specification.md`
- Modify: `docs/specifications/CHANGELOG.md`
- Modify: All topic files version headers and `docs/README.md`
- Test: `tests/contract/test_schema_fixtures.py`, `scripts/generate_contracts.py --check`

- [ ] **Step 1: Write ADR-074**
  - Document choice of `linear_pattern` IR node, direction specification (`plane:right`, `plane:top`, or axes), instance count, spacing in mm, and `CreateDefinition(swFmLPattern)` in C# adapter.
- [ ] **Step 2: Update JSON Schemas**
  - Create `schemas/part-feature-graph/features/linear_pattern.json` with `seeds`, `direction_1` (`direction`, `spacing`, `count`, `reverse`), optional `direction_2`.
  - Add `linear_pattern` to `schemas/part-feature-graph/v0.json` node union.
  - Update `schemas/ipc/ops/feature.create.json` to allow `type: "linear_pattern"`.
- [ ] **Step 3: Regenerate Contracts**
  - Run `uv run python scripts/generate_contracts.py`.
  - Verify `generate_contracts.py --check` passes with zero drift.
- [ ] **Step 4: Bump Spec Version to v1.43**
  - Bump header in all 32 topic files, `docs/README.md`, `docs/specifications/README.md`.
  - Add v1.43 entry to `docs/specifications/CHANGELOG.md`.
- [ ] **Step 5: Verify & Commit Task 1**
  - Run `uv run ruff check` and `uv run pytest tests/contract/test_schema_fixtures.py`.
  - Commit Task 1.

---

### Task 2: Pure Core IR & Compiler Lowering (`cad-ir` & `cad-compiler`)

**Files:**
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/model.py`
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/__init__.py`
- Modify: `packages/cad-compiler/src/cad_compiler/validator/semantic.py`
- Modify: `packages/cad-compiler/src/cad_compiler/lowering/lower.py`
- Test: `packages/cad-ir/tests/test_part_feature_graph.py`
- Test: `packages/cad-compiler/tests/test_rules.py`
- Test: `packages/cad-compiler/tests/test_compile.py`

- [ ] **Step 1: Write failing tests for LinearPattern model, parsing, validation, and lowering**
  - In `test_part_feature_graph.py`: test parsing valid `LinearPattern` node.
  - In `test_rules.py`: test semantic validation (seeds exist, count >= 2, spacing >= 0.01).
  - In `test_compile.py`: test compilation of graph with `linear_pattern` producing `feature.create` operation.
- [ ] **Step 2: Implement dataclass & parser in `cad-ir`**
  - Define `LinearPatternDirection` and `LinearPattern` dataclasses in `model.py`.
  - Add parsing in `parse.py` and export in `__init__.py`.
- [ ] **Step 3: Implement semantic validation in `cad-compiler`**
  - In `semantic.py`: validate seed dependencies, spacing, count, and pattern bounds.
- [ ] **Step 4: Implement lowering in `cad-compiler`**
  - In `lower.py`: lower `LinearPattern` into `feature.create` op with `seeds`, `direction_1`, `direction_2`.
- [ ] **Step 5: Verify & Commit Task 2**
  - Run `uv run pytest packages/cad-ir packages/cad-compiler`.
  - Commit Task 2.

---

### Task 3: Verification Engine Geometry (`cad-verification`)

**Files:**
- Modify: `packages/cad-verification/src/cad_verification/part.py`
- Modify: `packages/cad-verification/src/cad_verification/api/contracts.py`
- Test: `packages/cad-verification/tests/test_part.py`

- [ ] **Step 1: Write failing tests for expected geometry with linear pattern**
  - Test expected volume on plate with patterned cut holes: $V = V_{\text{base}} - N \cdot V_{\text{hole}}$.
  - Test expected cylinders: $N$ cylinders of diameter $D$.
- [ ] **Step 2: Implement pattern geometry calculation in `part.py`**
  - In `expected_geometry`: detect `LinearPattern` nodes, compute total instance multiplier $N = N_1 \times (N_2 \text{ or } 1)$.
  - Deduct $N \times V_{\text{seed}}$ from base volume. Replicate seed cylinders $N$ times.
- [ ] **Step 3: Update contract verification in `contracts.py`**
  - Account for pattern features in expected feature counts.
- [ ] **Step 4: Verify & Commit Task 3**
  - Run `uv run pytest packages/cad-verification`.
  - Commit Task 3.

---

### Task 4: C# Execution Engine Adapters (`ExecutionServer.Core` & `ExecutionServer.Adapters`)

**Files:**
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs`
- Modify: `apps/execution-server/ExecutionServer.Tests/Parts/FeatureAdapterTests.cs` (or create if needed)
- Test: `apps/execution-server/ExecutionServer.Tests`

- [ ] **Step 1: Write tests in `ExecutionServer.Tests` for `feature.create` deserialization**
  - Validate `FeatureCreateParams` deserialization for `type: "linear_pattern"`, `seeds`, and `direction_1`.
- [ ] **Step 2: Implement handler in `FeatureAdapter.cs`**
  - When `p.Type == FeatureCreateParamsType.LinearPattern`:
    - Resolve seed feature(s) via `FeatureLookup.FindById`.
    - Resolve direction axis/plane via `DocumentLocator` or standard plane lookup.
    - Call `doc.FeatureManager.CreateDefinition((int)swFeatureNameID_e.swFmLPattern)`.
    - Set `D1Axis`, `D1Spacing`, `D1TotalInstances`, `D1ReverseDirection`, `PatternFeatureArray = new object[] { seedFeat }`.
    - Call `doc.FeatureManager.CreateFeature(featData)`.
    - Track and clean up temporary COM objects in `ComScope`.
- [ ] **Step 3: Verify C# unit tests and build**
  - Run `dotnet test apps/execution-server/ExecutionServer.Tests`.
  - Run `dotnet build apps/execution-server/ExecutionServer.sln -c Release` and `-c Debug`.
  - Commit Task 4.

---

### Task 5: Authoring Guide & Benchmark Suite (`cad-application` & `tests/cad-benchmark`)

**Files:**
- Modify: `packages/cad-application/src/cad_application/authoring_guide.py`
- Modify: `packages/cad-application/src/cad_application/authoring_eval/cases.py`
- Modify: `packages/cad-application/src/cad_application/authoring_eval/references.py`
- Modify: `tests/cad-benchmark/part_ir_baseline_answers.json`
- Test: `tests/cad-benchmark/test_part_ir_benchmark.py`

- [ ] **Step 1: Update authoring guide**
  - In `authoring_guide.py`: add `linear_pattern` to supported types and rules. Update `_UNSUPPORTED` to remove linear pattern.
  - Add worked example with linear patterned hole cut.
- [ ] **Step 2: Add/update benchmark case**
  - In `cases.py`: add `plate_pattern_holes` case (e.g. 100 x 60 x 10 plate with 4 patterned holes).
  - In `references.py`: add reference answer for `plate_pattern_holes`.
  - Update `part_ir_baseline_answers.json`.
- [ ] **Step 3: Verify benchmark scoring**
  - Run `uv run python scripts/score_part_ir.py tests/cad-benchmark/part_ir_baseline_answers.json`.
  - Expect 16/16 cases passing.
  - Commit Task 5.

---

### Task 6: Live SOLIDWORKS Verification & Promotion (`tests/live`, checklists)

**Files:**
- Modify: `tests/live/test_live_part_chain.py`
- Modify: `docs/implementation/part-features/patterns-mirrors.md`
- Modify: `HANDOFF.md`
- Test: Full verification suite (`pytest tests/live -m live`, `check_implementation_checklists.py`)

- [ ] **Step 1: Add live acceptance tests**
  - In `test_live_part_chain.py`: add `test_live_linear_pattern_plate` verifying end-to-end creation and measurement against SOLIDWORKS 2025.
  - Add direct IPC test `test_live_direct_linear_pattern_ops`.
  - Run live tests and confirm pass.
- [ ] **Step 2: Promote checklist items**
  - In `patterns-mirrors.md`: promote `PAT-LIN-001`, `PAT-LIN-002`, `PAT-LIN-003`, `PAT-LIN-004` to `Verified`.
  - Run `uv run python scripts/check_implementation_checklists.py --write`.
- [ ] **Step 3: Run full verification suite**
  - Contracts check, ruff check, ruff format check, pyright, lint-imports, pytest, dotnet test.
- [ ] **Step 4: Update `HANDOFF.md` and commit Task 6**
  - Rewrite `HANDOFF.md` in place per AGENTS.md §5 rules.
  - Commit Task 6.
