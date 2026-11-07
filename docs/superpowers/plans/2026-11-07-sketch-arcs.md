# Sketch Arc Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the 3D Part Feature Graph IR, compiler, verifier, C# add-in adapters, and evaluation suite to support sketch arc primitives (`SK-ENT-013`, `SK-ENT-014`, `SK-ENT-016`), enabling closed loops of lines and arcs (slots, rounded corners, curved tabs) for extrusions and cuts.

**Architecture:** Pure-core / port-adapter / STA add-in layering (Guideline G1, G2, ADR-035, ADR-038, ADR-059, ADR-071). Define schema contract for `Arc` in `schemas/`, lower into `sketch.create` entity payload, implement COM-safe `ISketchManager.CreateArc` in `SketchAdapter`, compute exact expected bounding box and volume in `cad-verification`, and add benchmark cases under `tests/cad-benchmark`.

**Tech Stack:** Python 3.12+ (`uv`, `pytest`, `ruff`, `pyright`, `lint-imports`), C# / .NET (`ExecutionServer.Core` netstandard2.0, `ExecutionServer.Adapters` / `ExecutionServer.AddIn` net48, `ExecutionServer.Tests` net8.0 xUnit), SOLIDWORKS 2025 COM interop.

**Spec:** [`docs/specifications/README.md`](../../specifications/README.md) (v1.40), [`docs/specifications/ir-specification.md`](../../specifications/ir-specification.md) (§22.4.1), [`docs/architecture/feature-schema-guide.md`](../../architecture/feature-schema-guide.md) (§5.7.4), [`docs/adr/ADR-071-sketch-arc-primitives.md`](../../adr/ADR-071-sketch-arc-primitives.md), [`docs/implementation/sketch/sketch-entities.md`](../../implementation/sketch/sketch-entities.md).

## Global Constraints

- **Freeze 2D drawings (ADR-057):** Do **not** modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas in `schemas/`, `tests/drawing-benchmark`, or any drawing live tests.
- **Custody of source files (ADR-022):** Never write to source parts or assemblies without permission.
- **Schema-first contracts (ADR-035):** Edit schemas in `schemas/`. Run `python scripts/generate_contracts.py` to regenerate Python models and C# types; never edit generated files by hand.
- **Python layering & purity (Guideline G2):** Pure packages (`cad-ir`, `cad-compiler`, `cad-verification`, `cad-references`, `cad-geometry`) perform zero I/O and have zero CAD vendor imports.
- **C# COM object safety (Guideline G1, ADR-059):** Release temporary COM objects (`ISketchSegment`, `ISketchArc`) via `Marshal.ReleaseComObject` in `finally` blocks or `ComScope`. Never release `ISldWorks`, `IModelDoc2`, or manager objects. Never call `Marshal.FinalReleaseComObject`.
- **ExecutionServer.Core CAD-free (ADR-038):** Zero SOLIDWORKS references in `ExecutionServer.Core`; enforced by `BannedSymbols.txt`.

## Review Focus

1. **Arc geometry validation:** Arc start and end points must be equidistant from the center point within numerical quantum ($10^{-6}$ mm), radius $\ge 0.01$ mm, and start != end.
2. **Profile loop closure with mixed lines and arcs:** `_chain_entities_into_loop` in `semantic.py` must chain alternating `Line` and `Arc` segments where end of entity $i$ matches start of entity $i+1$, detecting closed loops and refusing unclosed profiles.
3. **Exact area & volume computation with arcs:** `expected_geometry` in `cad-verification` must compute exact cross-sectional area for profiles with circular arcs (Green's theorem with arc segments or polygon + circular segments) and correct 3D bounding boxes spanning arc extrema.
4. **C# COM wrapper cleanup:** `SketchAdapter.CreateSketch` must wrap `sm.CreateArc` in COM cleanup (`Marshal.ReleaseComObject`), matching `CreateLine` and `CreateCircleByRadius`.
5. **Authoring guide & benchmark sync:** Update `authoring_guide.py` rules and examples, add `plate_rounded_slot` to `cases.py`, and ensure `score_part_ir.py` passes all benchmark cases.

---

### Task 1: Spec & Schemas (ADR-071, Schemas, Spec v1.40)

**Files:**
- Create: `docs/adr/ADR-071-sketch-arc-primitives.md`
- Modify: `docs/specifications/README.md`
- Modify: `docs/specifications/CHANGELOG.md`
- Modify: `docs/specifications/ir-specification.md`
- Modify: `schemas/part-feature-graph/v0.json`
- Modify: `schemas/execution-plan/v0.json`
- Modify: `docs/implementation/sketch/sketch-entities.md`
- Generate: `packages/cad-ir/src/cad_ir/generated/` & `apps/execution-server/ExecutionServer.Core/Ipc/Generated/`

- [ ] **Step 1: Write ADR-071**
  Document the decision to represent sketch arcs via `center`, `start`, `end`, and `direction` (`"ccw"` / `"cw"`), aligning with `ISketchManager.CreateArc(xc, yc, zc, xp1, yp1, zp1, xp2, yp2, zp2, Dir)`.
- [ ] **Step 2: Update JSON Schemas**
  In `schemas/part-feature-graph/v0.json`, add `$defs/Arc` and include it in `$defs/SketchEntity`. In `schemas/execution-plan/v0.json`, add `arc` entity format to `SketchCreateEntity`.
- [ ] **Step 3: Regenerate contracts and bump spec version**
  Run `uv run python scripts/generate_contracts.py`. Bump spec version to v1.40 in `docs/specifications/README.md`, `ir-specification.md`, and log in `CHANGELOG.md`.
- [ ] **Step 4: Update implementation checklists & audit**
  Update `docs/implementation/sketch/sketch-entities.md` rows `SK-ENT-013` and `SK-ENT-016`. Run `uv run python scripts/check_implementation_checklists.py --write`.

---

### Task 2: Pure Core IR & Compiler Support (`cad-ir` & `cad-compiler`)

**Files:**
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/model.py`
- Modify: `packages/cad-compiler/src/cad_compiler/validator/semantic.py`
- Modify: `packages/cad-compiler/src/cad_compiler/lowering/lower.py`
- Test: `packages/cad-ir/tests/test_part_feature_graph.py`
- Test: `packages/cad-compiler/tests/test_rules.py`
- Test: `packages/cad-compiler/tests/test_lower.py`

- [ ] **Step 1: Write failing tests for Arc model and semantic validation**
  Add unit tests in `packages/cad-ir/tests/test_part_feature_graph.py` and `packages/cad-compiler/tests/test_rules.py` testing valid arcs, unequal radii, zero radius, and loops mixing lines and arcs.
  Expected: Tests fail because `Arc` is not defined or validator does not support arcs.
- [ ] **Step 2: Implement `Arc` dataclass in `cad_ir`**
  Add `Arc` with `center`, `start`, `end`, `direction`, and `to_dict()`. Update `SketchNode.entities` union.
- [ ] **Step 3: Implement arc validation and loop chaining in `cad_compiler`**
  In `semantic.py`: validate arc radii equality, positive radius, distinct start/end; update `_validate_lines_loop` / `_chain_lines_into_loop` to support both lines and arcs forming closed loops.
- [ ] **Step 4: Lower `Arc` in `cad_compiler`**
  In `lowering/lower.py`: lower `Arc` instances into `sketch.create` operation entities with `type: "arc"`, `center`, `start`, `end`, `direction`.
- [ ] **Step 5: Run tests and verify GREEN**
  Run `uv run pytest packages/cad-ir packages/cad-compiler` and ensure all pass.

---

### Task 3: Verification Engine Geometry & Expectation (`cad-verification`)

**Files:**
- Modify: `packages/cad-verification/src/cad_verification/part.py`
- Test: `packages/cad-verification/tests/test_part.py`

- [ ] **Step 1: Write failing tests for expected geometry with arcs**
  Add unit tests in `packages/cad-verification/tests/test_part.py` for an extruded slot/rounded rectangle (lines + two semicircular arcs): test expected bounding box, volume, and cylindrical faces.
  Expected: Fails because `expected_geometry` does not handle `Arc`.
- [ ] **Step 2: Implement arc bounding box & area calculation**
  In `cad_verification/part.py`:
  - Calculate 2D bounding box of arc including cardinal extrema (0, $\pi/2$, $\pi$, $3\pi/2$) contained in the arc's angular span.
  - Calculate cross-sectional area: polygon area from chord vertices + signed circular segment areas $\frac{1}{2} R^2 (\theta - \sin \theta)$.
  - Register `ExpectedCylinder` faces for each extruded arc.
- [ ] **Step 3: Run verification tests and verify GREEN**
  Run `uv run pytest packages/cad-verification` and ensure all pass.

---

### Task 4: C# Execution Engine Adapters (`ExecutionServer.Core` & `ExecutionServer.Adapters`)

**Files:**
- Modify: `apps/execution-server/ExecutionServer.Core/Parts/SketchCreateEntity.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/Parts/SketchAdapterTests.cs`

- [ ] **Step 1: Write failing tests for C# Arc deserialization and lowering**
  Add unit tests in `ExecutionServer.Tests` verifying `SketchCreateEntity` deserializes `Arc` with center, start, end, and direction.
  Expected: Fails or fails to compile until properties are defined.
- [ ] **Step 2: Update `SketchCreateEntity` in `ExecutionServer.Core`**
  Add `SketchCreateEntityType.Arc`, `Center`, `Start`, `End`, `Direction`.
- [ ] **Step 3: Implement `sm.CreateArc` in `SketchAdapter.cs`**
  Convert millimetres to metres; call `sm.CreateArc(xc, yc, 0, xp1, yp1, 0, xp2, yp2, 0, dir)`; release COM object via `Marshal.ReleaseComObject`.
- [ ] **Step 4: Build and test C# solution**
  Run `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`.

---

### Task 5: Authoring Guide & Benchmark Suite (`cad-application` & `tests/cad-benchmark`)

**Files:**
- Modify: `packages/cad-application/src/cad_application/authoring_guide.py`
- Modify: `packages/cad-application/src/cad_application/authoring_eval/cases.py`
- Modify: `tests/cad-benchmark/part_ir_baseline_answers.json`
- Modify: `packages/cad-application/tests/test_authoring_guide.py`
- Modify: `tests/cad-benchmark/test_part_ir_benchmark.py`

- [ ] **Step 1: Update authoring guide**
  Update `_RULES` with arc rules, remove arcs from `_UNSUPPORTED`, add a slot/rounded plate example.
- [ ] **Step 2: Add benchmark case with arcs**
  Add `plate_slot` (e.g. 60 × 40 × 10 mm plate with a 30 × 10 mm rounded slot or rounded ends) to `cases.py`.
- [ ] **Step 3: Update baseline answers and score benchmark**
  Add the valid IR graph in `part_ir_baseline_answers.json`. Run `uv run python scripts/score_part_ir.py tests/cad-benchmark/part_ir_baseline_answers.json`.
  Expected: 14/14 cases pass.

---

### Task 6: Full Verification Suite & Handoff

**Files:**
- Modify: `docs/implementation/README.md`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Run full Python verification suite**
  ```bash
  uv run python scripts/generate_contracts.py --check
  uv run ruff check
  uv run ruff format --check
  uv run pyright
  uv run lint-imports
  uv run pytest --ignore=tests/drawing-benchmark
  uv run python scripts/check_implementation_checklists.py
  ```
- [ ] **Step 2: Run C# verification**
  ```bash
  dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj
  dotnet build apps/execution-server/ExecutionServer.sln -c Release
  ```
- [ ] **Step 3: Update documentation and checklists**
  Update checklist statuses in `docs/implementation/sketch/sketch-entities.md`. Refresh derived summary via `scripts/check_implementation_checklists.py --write`. Update `HANDOFF.md` with latest state and test counts.
