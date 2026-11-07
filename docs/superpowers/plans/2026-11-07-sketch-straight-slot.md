# Sketch Straight Slot Primitive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand 3D Part feature capabilities by introducing first-class Sketch Straight Slot primitives (`SK-ENT-021`) across schemas, pure core IR/compiler lowering, verification geometry, execution adapter, authoring benchmark, and live SOLIDWORKS 2025 verification.

**Architecture:** Pure-core / port-adapter / STA add-in layering (Guideline G1, G2, ADR-010, ADR-035, ADR-038, ADR-059, ADR-070, ADR-072, ADR-073). Define schema contracts for `straight_slot` (`start_point`, `end_point`, `width`) in `schemas/`, validate in `cad-compiler`, lower deterministically into CCW 2-line + 2-arc loops in `cad-compiler`, compute closed-form geometric properties in `cad-verification`, execute in C# `SketchAdapter.cs` with COM cleanup, upgrade `plate_slot` in authoring benchmark, and verify against live SOLIDWORKS 2025 in `tests/live/test_live_part_chain.py`.

**Tech Stack:** Python 3.12+ (`uv`, `pytest`, `ruff`, `pyright`, `lint-imports`), C# / .NET (`ExecutionServer.Core` netstandard2.0, `ExecutionServer.Adapters` / `ExecutionServer.AddIn` net48, `ExecutionServer.Tests` net8.0 xUnit), SOLIDWORKS 2025 COM interop.

**Spec:** [`docs/specifications/README.md`](../../specifications/README.md) (v1.42), [`docs/specifications/ir-specification.md`](../../specifications/ir-specification.md) (§22.4.1), [`docs/architecture/feature-schema-guide.md`](../../architecture/feature-schema-guide.md) (§5.7.4), [`docs/adr/ADR-073-sketch-straight-slot-primitive.md`](../../adr/ADR-073-sketch-straight-slot-primitive.md), [`docs/implementation/sketch/sketch-entities.md`](../../implementation/sketch/sketch-entities.md).

## Global Constraints

- **Freeze 2D drawings (ADR-057):** Do **not** modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas in `schemas/`, `tests/drawing-benchmark`, or any drawing live tests.
- **Custody of source files (ADR-022):** Never write to source parts or assemblies without permission.
- **Schema-first contracts (ADR-035):** Edit schemas in `schemas/`. Run `python scripts/generate_contracts.py` to regenerate Python models and C# types; never edit generated files by hand.
- **Python layering & purity (Guideline G2):** Pure packages (`cad-ir`, `cad-compiler`, `cad-verification`, `cad-references`, `cad-geometry`) perform zero I/O and have zero CAD vendor imports.
- **C# COM object safety (Guideline G1, ADR-059):** Release temporary COM objects (`ISketchSegment`) via `Marshal.ReleaseComObject` in `finally` blocks or `ComScope`. Never release `ISldWorks`, `IModelDoc2`, or manager objects. Never call `Marshal.FinalReleaseComObject`.
- **ExecutionServer.Core CAD-free (ADR-038):** Zero SOLIDWORKS references in `ExecutionServer.Core`; enforced by `BannedSymbols.txt`.

## Review Focus

1. **Straight slot geometric validation:** Centerline length $L = \sqrt{(x_2-x_1)^2 + (y_2-y_1)^2} \ge 0.01$ mm and slot `width` $W \ge 0.01$ mm. Degenerate or negative parameters must be rejected with descriptive diagnostic messages.
2. **Deterministic CCW loop lowering:** Lowering `straight_slot` produces 4 ordered, tangent entities oriented counter-clockwise: Line 1 (tangent side 1), Arc 1 (semicircular cap 1, CCW), Line 2 (tangent side 2), Arc 2 (semicircular cap 2, CCW). Loop closure endpoints must align within 1e-6 mm without numerical gap.
3. **Cap-face sketch frame transformation:** Sketches placed on `<extrude>.start_face` or `<extrude>.end_face` must transform both centerline endpoints and slot dimensions according to ADR-070 face reflection rules.
4. **Exact area & volume computation:** `expected_geometry` in `cad-verification` must calculate exact closed-form area $A = L \cdot W + \frac{\pi}{4} W^2$, perimeter $P = 2 L + \pi W$, symmetric center of mass, and bounding box extents for slot profiles.
5. **Live SOLIDWORKS verification & checklist promotion:** Verify slot creation live against SOLIDWORKS 2025 with end-to-end extrusion and promote `SK-ENT-021` to `Verified` with zero audit errors.

---

### Task 1: Spec & Schemas (ADR-073, Schemas, Spec v1.42)

**Files:**
- Create: `docs/adr/ADR-073-sketch-straight-slot-primitive.md`
- Modify: `docs/specifications/README.md`
- Modify: `docs/specifications/CHANGELOG.md`
- Modify: `docs/specifications/ir-specification.md`
- Modify: `docs/architecture/feature-schema-guide.md`
- Modify: `schemas/part-feature-graph/v0.json`
- Modify: `schemas/ipc/ops/sketch.create.json`
- Modify: `docs/implementation/sketch/sketch-entities.md`
- Generate: `packages/cad-ir/src/cad_ir/generated/` & `apps/execution-server/ExecutionServer.Core/Ipc/Generated/`

- [ ] **Step 1: Write ADR-073**
  Draft `docs/adr/ADR-073-sketch-straight-slot-primitive.md` specifying `straight_slot` defined by centerline endpoints `start_point: [x1, y1]`, `end_point: [x2, y2]`, and full slot `width: float` ($W \ge 0.01$ mm), lowering deterministically to 2 parallel lines and 2 semicircular CCW arcs.
- [ ] **Step 2: Update JSON Schemas**
  In `schemas/part-feature-graph/v0.json`, define `$defs/StraightSlot` and include it in `$defs/SketchEntity`. In `schemas/ipc/ops/sketch.create.json`, include `straight_slot` in `$defs/Entity`.
- [ ] **Step 3: Regenerate contracts and bump spec version**
  Run `uv run python scripts/generate_contracts.py`. Bump spec version to v1.42 across topic files and document changes in `docs/specifications/CHANGELOG.md`.
- [ ] **Step 4: Update implementation checklists**
  In `docs/implementation/sketch/sketch-entities.md`, update `SK-ENT-021` status to `Specified`. Run `uv run python scripts/check_implementation_checklists.py --write`.

---

### Task 2: Pure Core IR & Compiler Lowering (`cad-ir` & `cad-compiler`)

**Files:**
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/model.py`
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/parse.py`
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/faces.py`
- Modify: `packages/cad-compiler/src/cad_compiler/validator/semantic.py`
- Modify: `packages/cad-compiler/src/cad_compiler/lowering/lower.py`
- Test: `packages/cad-ir/tests/test_part_feature_graph.py`
- Test: `packages/cad-ir/tests/test_faces.py`
- Test: `packages/cad-compiler/tests/test_rules.py`
- Test: `packages/cad-compiler/tests/test_compile.py`

- [ ] **Step 1: Write failing unit tests for StraightSlot models, parsing, and validation**
  Add unit tests in `packages/cad-ir/tests/test_part_feature_graph.py` and `packages/cad-compiler/tests/test_rules.py` for valid slots, degenerate zero-length centerline ($P_1 = P_2$), zero/negative width ($W \le 0$), and closed loop profile validation.
  Expected: FAIL.
- [ ] **Step 2: Implement dataclass in `cad_ir`**
  Add `StraightSlot` dataclass in `model.py` (`start_point`, `end_point`, `width`) with `to_dict()`, update `SketchEntity` union, and update `parse.py` to parse `StraightSlot`.
- [ ] **Step 3: Implement semantic validation in `cad_compiler`**
  In `semantic.py`, validate straight slot dimensions ($L \ge 0.01$ mm, $W \ge 0.01$ mm). Support `straight_slot` as an inherently closed, non-self-intersecting profile loop.
- [ ] **Step 4: Support face reflection in `cad_ir/part_feature_graph/faces.py`**
  Handle coordinate mirroring and transformation of `StraightSlot` when sketch is placed on `<extrude>.start_face` or `<extrude>.end_face`.
- [ ] **Step 5: Implement deterministic CCW lowering in `cad_compiler`**
  In `lowering/lower.py`, lower `StraightSlot` into 2 `Line` entities and 2 `Arc` entities with exact tangent offsets:
  $$L = \sqrt{\Delta x^2 + \Delta y^2}, \quad \hat{u} = (\Delta x/L, \Delta y/L), \quad \hat{n} = (-\Delta y/L, \Delta x/L), \quad r = W / 2$$
  - Line 1: $(P_1 - r\hat{n}) \to (P_2 - r\hat{n})$
  - Arc 1 (cap at $P_2$): center $P_2$, from $(P_2 - r\hat{n})$ to $(P_2 + r\hat{n})$, CCW
  - Line 2: $(P_2 + r\hat{n}) \to (P_1 + r\hat{n})$
  - Arc 2 (cap at $P_1$): center $P_1$, from $(P_1 + r\hat{n})$ to $(P_1 - r\hat{n})$, CCW
- [ ] **Step 6: Run tests and verify GREEN**
  Run `uv run pytest packages/cad-ir packages/cad-compiler` and confirm 100% pass.

---

### Task 3: Verification Engine Geometry (`cad-verification`)

**Files:**
- Modify: `packages/cad-verification/src/cad_verification/part.py`
- Modify: `packages/cad-verification/src/cad_verification/api/contracts.py`
- Test: `packages/cad-verification/tests/test_part.py`

- [ ] **Step 1: Write failing tests for expected geometry with straight slots**
  In `packages/cad-verification/tests/test_part.py`, test expected volume, bounding box, perimeter, and area for an extrusion built with a `straight_slot`.
  Expected: FAIL (`expected_geometry` does not yet recognize `StraightSlot`).
- [ ] **Step 2: Implement closed-form slot geometry in `cad_verification/part.py`**
  Calculate exact area $A = L \cdot W + \frac{\pi}{4} W^2$, perimeter $P = 2 L + \pi W$, center of mass $(P_1 + P_2)/2$, and 2D/3D bounding boxes.
- [ ] **Step 3: Update `_sketch_entity_count` in `contracts.py`**
  Handle lowered segment count for slots (1 straight slot = 4 lowered segments) so contract verification accurately evaluates sketch entity counts.
- [ ] **Step 4: Run verification tests and verify GREEN**
  Run `uv run pytest packages/cad-verification` and confirm 100% pass.

---

### Task 4: C# Execution Engine Adapters (`ExecutionServer.Core` & `ExecutionServer.Adapters`)

**Files:**
- Modify: `apps/execution-server/ExecutionServer.Core/Parts/SketchCreateEntity.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/Parts/SketchAdapterTests.cs`

- [ ] **Step 1: Write failing tests in C# test suite**
  Add unit tests in `ExecutionServer.Tests` validating `SketchCreateEntity` deserialization for `straight_slot`.
- [ ] **Step 2: Update `SketchCreateEntity` in `ExecutionServer.Core`**
  Add `StraightSlot` enum value and `StraightSlotData` properties (`StartPoint`, `EndPoint`, `Width`) adhering to ADR-038.
- [ ] **Step 3: Implement handler in `SketchAdapter.cs`**
  In `SketchAdapter.cs`, handle `SketchCreateEntityType.StraightSlot` by either delegating to native `CreateSketchSlot` or creating the lowered 2 lines + 2 arcs, ensuring all created COM objects are strictly released with `Marshal.ReleaseComObject` in `finally` blocks (Guideline G1, ADR-059).
- [ ] **Step 4: Build and test C# solution**
  Run `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`.

---

### Task 5: Authoring Guide & Benchmark Suite (`cad-application` & `tests/cad-benchmark`)

**Files:**
- Modify: `packages/cad-application/src/cad_application/authoring_guide.py`
- Modify: `tests/cad-benchmark/part_ir_baseline_answers.json`
- Modify: `packages/cad-application/src/cad_application/authoring_eval/references.py`
- Test: `tests/cad-benchmark/test_part_ir_benchmark.py`

- [ ] **Step 1: Update authoring guide**
  Update `authoring_guide.py` to document `straight_slot` syntax, parameters, and worked examples.
- [ ] **Step 2: Update benchmark fixture `plate_slot`**
  Update `plate_slot` in `part_ir_baseline_answers.json` and `references.py` to use the native `straight_slot` primitive instead of manual 4-piece line/arc composition.
- [ ] **Step 3: Run benchmark scoring**
  Run `uv run python scripts/score_part_ir.py tests/cad-benchmark/part_ir_baseline_answers.json`.
  Expected: 15/15 passing (100%).

---

### Task 6: Live SOLIDWORKS Verification & Promotion (`tests/live`, checklists)

**Files:**
- Modify: `tests/live/test_live_part_chain.py`
- Modify: `docs/implementation/sketch/sketch-entities.md`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Update `test_live_slot_plate` in `test_live_part_chain.py`**
  Verify that `plate_slot` with native `straight_slot` primitive builds and commits cleanly with all geometry checks passing on live SOLIDWORKS 2025.
- [ ] **Step 2: Add direct slot IPC test `test_live_direct_slot_ops`**
  Add direct execution test calling `sketch.create` with `straight_slot` entity to verify adapter execution and COM lifecycle.
- [ ] **Step 3: Run live tests against SOLIDWORKS 2025**
  Run `uv run pytest tests/live/test_live_part_chain.py -k "slot" -m live`.
  Expected: PASS.
- [ ] **Step 4: Promote `SK-ENT-021` to `Verified`**
  In `docs/implementation/sketch/sketch-entities.md`, update `SK-ENT-021` to `Verified` with all checkmarks ✅.
  Run `uv run python scripts/check_implementation_checklists.py`.
- [ ] **Step 5: Full regression verification & handoff update**
  Run full verification: `uv run python scripts/generate_contracts.py --check`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run lint-imports`, `uv run pytest`, `dotnet test apps/execution-server`. Update `HANDOFF.md` with new status and metrics.
