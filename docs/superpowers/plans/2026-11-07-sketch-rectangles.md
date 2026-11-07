# Sketch Rectangle Primitives & Arc Live Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand 3D Part feature capabilities by introducing first-class Sketch Corner and Center Rectangle primitives (`SK-ENT-005`, `SK-ENT-006`) across schemas, pure core IR/compiler, verifier, and authoring suite, while adding a live integration test to promote Sketch Arcs (`SK-ENT-013`, `SK-ENT-016`) to `Verified` status against live SOLIDWORKS 2025.

**Architecture:** Pure-core / port-adapter / STA add-in layering (Guideline G1, G2, ADR-035, ADR-038, ADR-059, ADR-071, ADR-072). Define schema contracts for `corner_rectangle` (`corner1`, `corner2`) and `center_rectangle` (`center`, `width`, `height`) in `schemas/`, validate in `cad-compiler`, compute closed-form bounding box and area in `cad-verification`, lower to canonical closed line loops in `cad-compiler` / IPC operations, update authoring guide and eval benchmark in `cad-application`, and verify against live SOLIDWORKS 2025 in `tests/live/test_live_part_chain.py`.

**Tech Stack:** Python 3.12+ (`uv`, `pytest`, `ruff`, `pyright`, `lint-imports`), C# / .NET (`ExecutionServer.Core` netstandard2.0, `ExecutionServer.Adapters` / `ExecutionServer.AddIn` net48, `ExecutionServer.Tests` net8.0 xUnit), SOLIDWORKS 2025 COM interop.

**Spec:** [`docs/specifications/README.md`](../../specifications/README.md) (v1.41), [`docs/specifications/ir-specification.md`](../../specifications/ir-specification.md) (§22.4.1), [`docs/architecture/feature-schema-guide.md`](../../architecture/feature-schema-guide.md) (§5.7.4), [`docs/adr/ADR-072-sketch-rectangle-primitives.md`](../../adr/ADR-072-sketch-rectangle-primitives.md), [`docs/implementation/sketch/sketch-entities.md`](../../implementation/sketch/sketch-entities.md).

## Global Constraints

- **Freeze 2D drawings (ADR-057):** Do **not** modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas in `schemas/`, `tests/drawing-benchmark`, or any drawing live tests.
- **Custody of source files (ADR-022):** Never write to source parts or assemblies without permission.
- **Schema-first contracts (ADR-035):** Edit schemas in `schemas/`. Run `python scripts/generate_contracts.py` to regenerate Python models and C# types; never edit generated files by hand.
- **Python layering & purity (Guideline G2):** Pure packages (`cad-ir`, `cad-compiler`, `cad-verification`, `cad-references`, `cad-geometry`) perform zero I/O and have zero CAD vendor imports.
- **C# COM object safety (Guideline G1, ADR-059):** Release temporary COM objects (`ISketchSegment`) via `Marshal.ReleaseComObject` in `finally` blocks or `ComScope`. Never release `ISldWorks`, `IModelDoc2`, or manager objects. Never call `Marshal.FinalReleaseComObject`.
- **ExecutionServer.Core CAD-free (ADR-038):** Zero SOLIDWORKS references in `ExecutionServer.Core`; enforced by `BannedSymbols.txt`.

## Review Focus

1. **Rectangle geometry validation:** `corner_rectangle` requires `|x1 - x2| >= 0.01` mm and `|y1 - y2| >= 0.01` mm. `center_rectangle` requires `width >= 0.01` mm and `height >= 0.01` mm.
2. **Deterministic CCW loop lowering:** Lowering `corner_rectangle` and `center_rectangle` produces four ordered lines oriented counter-clockwise `(min_x, min_y) -> (max_x, min_y) -> (max_x, max_y) -> (min_x, max_y)` ensuring consistent outward normals and loop closure.
3. **Cap-face sketch frame transformation:** Sketches placed on `<extrude>.start_face` or `<extrude>.end_face` must transform rectangle coordinates cleanly without parity or coordinate inversion errors in `cad-references/faces.py`.
4. **Exact area & volume computation:** `expected_geometry` in `cad-verification` computes exact area `width * height`, 3D bounding box, and planar boundary faces for rectangular profiles.
5. **Live SOLIDWORKS verification:** Live suite `tests/live/test_live_part_chain.py` verifies both the newly added rectangles and the merged arcs against an interactive SOLIDWORKS 2025 instance.

---

### Task 1: Spec & Schemas (ADR-072, Schemas, Spec v1.41)

**Files:**
- Create: `docs/adr/ADR-072-sketch-rectangle-primitives.md`
- Modify: `docs/specifications/README.md`
- Modify: `docs/specifications/CHANGELOG.md`
- Modify: `docs/specifications/ir-specification.md`
- Modify: `docs/architecture/feature-schema-guide.md`
- Modify: `schemas/part-feature-graph/v0.json`
- Modify: `schemas/ipc/ops/sketch.create.json`
- Modify: `docs/implementation/sketch/sketch-entities.md`
- Generate: `packages/cad-ir/src/cad_ir/generated/` & `apps/execution-server/ExecutionServer.Core/Ipc/Generated/`

- [ ] **Step 1: Write ADR-072**
  Draft `docs/adr/ADR-072-sketch-rectangle-primitives.md` specifying `corner_rectangle` (defined by two diagonal 2D points `corner1` and `corner2`) and `center_rectangle` (defined by `center: [x, y]`, `width: Length`, `height: Length`), lowering deterministically to 4 CCW boundary lines.
- [ ] **Step 2: Update JSON Schemas**
  In `schemas/part-feature-graph/v0.json`, define `$defs/CornerRectangle` and `$defs/CenterRectangle`, and add them to `$defs/SketchEntity`. In `schemas/ipc/ops/sketch.create.json`, include `corner_rectangle` and `center_rectangle` in `$defs/Entity`.
- [ ] **Step 3: Regenerate contracts and bump spec version**
  Run `uv run python scripts/generate_contracts.py`. Bump spec version to v1.41 across topic files and document changes in `docs/specifications/CHANGELOG.md`.
- [ ] **Step 4: Update implementation checklists**
  In `docs/implementation/sketch/sketch-entities.md`, update `SK-ENT-005` and `SK-ENT-006` status to `Specified`. Run `uv run python scripts/check_implementation_checklists.py --write`.

---

### Task 2: Pure Core IR & Compiler Support (`cad-ir` & `cad-compiler`)

**Files:**
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/model.py`
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`
- Modify: `packages/cad-references/src/cad_references/semantic/faces.py`
- Modify: `packages/cad-compiler/src/cad_compiler/validator/semantic.py`
- Modify: `packages/cad-compiler/src/cad_compiler/lowering/lower.py`
- Test: `packages/cad-ir/tests/test_part_feature_graph.py`
- Test: `packages/cad-compiler/tests/test_rules.py`
- Test: `packages/cad-compiler/tests/test_lower.py`

- [ ] **Step 1: Write failing unit tests for Rectangle models and validation**
  Add unit tests in `packages/cad-ir/tests/test_part_feature_graph.py` and `packages/cad-compiler/tests/test_rules.py` for valid corner/center rectangles, zero/negative width or height, degenerate diagonal points, and loop closure.
  Expected: FAIL (models or validation rules not yet present).
- [ ] **Step 2: Implement dataclasses in `cad_ir`**
  Add `CornerRectangle` and `CenterRectangle` dataclasses in `model.py` with `to_dict()` and update `SketchEntity` union. Update `parse.py` to instantiate them.
- [ ] **Step 3: Implement semantic validation in `cad_compiler`**
  In `semantic.py`, validate rectangle dimensions (minimum 0.01 mm, distinct corners). Support rectangles in sketch profile loop closure (a single rectangle forms a valid closed profile).
- [ ] **Step 4: Support face reflection in `cad_references`**
  In `cad_references/semantic/faces.py`, handle mirroring and coordinate transformation of `CornerRectangle` and `CenterRectangle` when hosted on `<extrude>.start_face`.
- [ ] **Step 5: Implement lowering in `cad_compiler`**
  In `lowering/lower.py`, lower `CornerRectangle` and `CenterRectangle` into 4 CCW `Line` entities (or native entity structures) in `sketch.create`.
- [ ] **Step 6: Run tests and verify GREEN**
  Run `uv run pytest packages/cad-ir packages/cad-compiler packages/cad-references` and confirm 100% pass.

---

### Task 3: Verification Engine Geometry & Expectation (`cad-verification`)

**Files:**
- Modify: `packages/cad-verification/src/cad_verification/part.py`
- Test: `packages/cad-verification/tests/test_part.py`

- [ ] **Step 1: Write failing tests for expected geometry with rectangles**
  In `packages/cad-verification/tests/test_part.py`, test expected volume, bounding box, and 6 bounding planar faces for an extrusion built with a `corner_rectangle` and another with a `center_rectangle`.
  Expected: FAIL (`expected_geometry` doesn't handle rectangle primitives).
- [ ] **Step 2: Implement rectangle area, bounding box, and face derivation**
  In `cad_verification/part.py`, implement closed-form 2D bounds and area for `CornerRectangle` and `CenterRectangle`, and generate expected planar faces for extrusions.
- [ ] **Step 3: Run verification tests and verify GREEN**
  Run `uv run pytest packages/cad-verification` and confirm 100% pass.

---

### Task 4: C# Execution Engine Adapters (`ExecutionServer.Core` & `ExecutionServer.Adapters`)

**Files:**
- Modify: `apps/execution-server/ExecutionServer.Core/Parts/SketchCreateEntity.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/Parts/SketchAdapterTests.cs`

- [ ] **Step 1: Write failing tests in C# test suite**
  Add tests in `ExecutionServer.Tests` verifying `SketchCreateEntity` deserializes `corner_rectangle` and `center_rectangle`.
- [ ] **Step 2: Update `SketchCreateEntity` in `ExecutionServer.Core`**
  Add entity types and fields for corner/center rectangles.
- [ ] **Step 3: Implement handler in `SketchAdapter.cs`**
  Handle rectangle entity dispatch in `SketchAdapter.cs`, converting coordinates to metres and releasing any created COM segments via `Marshal.ReleaseComObject`.
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
  Update `authoring_guide.py` with `corner_rectangle` and `center_rectangle` usage patterns and worked examples.
- [ ] **Step 2: Add benchmark test cases**
  Add benchmark cases utilizing rectangle entities to `cases.py` and `part_ir_baseline_answers.json`.
- [ ] **Step 3: Verify authoring benchmark green**
  Run `uv run python scripts/score_part_ir.py tests/cad-benchmark/part_ir_baseline_answers.json`.
  Expected: 100% passing.

---

### Task 6: Live SOLIDWORKS Verification & Promotion (`tests/live`, checklists)

**Files:**
- Modify: `tests/live/test_live_part_chain.py`
- Modify: `docs/implementation/sketch/sketch-entities.md`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Add live test for Arc primitive (`test_live_slot_plate`)**
  In `tests/live/test_live_part_chain.py`, add a live test that builds `plate_slot` (using `arc` and `line` entities) to verify `CreateArc` against SOLIDWORKS 2025.
- [ ] **Step 2: Add live test for Rectangle primitives (`test_live_rectangle_plate`)**
  In `tests/live/test_live_part_chain.py`, add a live test building a plate using `center_rectangle` with a cutout using `corner_rectangle`.
- [ ] **Step 3: Execute live test suite**
  Run `uv run pytest tests/live/test_live_part_chain.py -m live`.
  Expected: PASS on both arc and rectangle live tests.
- [ ] **Step 4: Promote checklists and audit**
  In `docs/implementation/sketch/sketch-entities.md`:
  - Promote `SK-ENT-013` (Center-point arc) and `SK-ENT-016` (Arc direction) from `Tested` to `Verified`.
  - Promote `SK-ENT-005` (Corner rectangle) and `SK-ENT-006` (Center rectangle) to `Verified`.
  Run `uv run python scripts/check_implementation_checklists.py`.
- [ ] **Step 5: Full verification and handoff update**
  Run the complete verification suite (`generate_contracts.py --check`, `ruff`, `pyright`, `lint-imports`, `pytest`, `dotnet test`). Update `HANDOFF.md` with current state and verification counts.
