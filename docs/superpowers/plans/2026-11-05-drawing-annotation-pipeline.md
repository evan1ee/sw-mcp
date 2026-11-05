# Phase 1c: Annotation & Dimension Placement Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the end-to-end annotation and dimension placement pipeline for drawings: import model dimensions (`model_items.insert`), insert ISO 128 center marks (`center_mark.add`), resolve dimension schemes (`DrawingIntent` and `ResolvedScheme`), hide duplicates and non-functional dimensions (`dimension.hide`), auto-arrange dimensions (`dimensions.auto_arrange`), and verify that the resulting drawing passes geometric hard checks D1, D2, D3, D5, and D7 with 0 violations live in SOLIDWORKS 2025 SP0.1.

**Architecture:**
- **Layer 1 (Schemas & IR Contracts):** Add `schemas/drawing-intent/v0.json` (Spec §11.10), `schemas/resolved-scheme/v0.json` (§11.10.1), and IPC ops (`model_items.insert`, `dimensions.auto_arrange`, `center_mark.add`, `dimension.hide`, `dimension.show`, `dimension.move`). Generate C# message types and Python Pydantic models; bump specification version to v1.27.
- **Layer 2 (Pure Python IR & Schemes):** Implement typed dataclasses and validators for `DrawingIntent` and `ResolvedScheme` in `packages/cad-ir/`. Implement pure dimension scheme resolution, duplicate identification, and gap-filling algorithms in `packages/cad-drawing/` (zero I/O, zero CAD imports, Guideline G2).
- **Layer 3 (C# Execution Engine):** Implement CAD-free `AnnotationPlacementMath.cs` in `ExecutionServer.Core` (ADR-038). Implement `AnnotationPlacementAdapter.cs` in `ExecutionServer.Adapters` using `IDrawingDoc.InsertModelAnnotations3()`, `IView.AutoInsertCenterMarks2()`, `IModelDocExtension.AlignDimensions((int)swAlignDimensionType_AutoArrange, spacing)`, and `IAnnotation.Visible = swAnnotationHidden`, adhering strictly to Guideline G1 (`Marshal.ReleaseComObject` in `finally` blocks). Wire operations into `SwAddin.cs`.
- **Layer 4 (Application & Live Validation):** Implement `cad_application.drawing.annotation_ops` to translate intent and snapshot geometry into backend operations. Implement live integration test `test_live_annotation_pipeline.py` exercising the full pipeline against SOLIDWORKS 2025 SP0.1, verifying that checks D1 (crossing), D2 (overlap), D3 (text over geometry), D5 (duplicates), and D7 (sheet boundary) pass with 0 violations.

**Tech Stack:** Python 3.13, C# / .NET Framework 4.8, SOLIDWORKS 2025 API (`IDrawingDoc`, `IView`, `IDisplayDimension`, `IAnnotation`), pytest, xUnit.

**Spec Reference:**
- [Spec §11.4: Drawing Pipeline](file:///d:/01_Data/code/sw-mcp/docs/architecture/production-drawings.md#114-pipeline)
- [Spec §11.5: Hard Checks D1–D10](file:///d:/01_Data/code/sw-mcp/docs/architecture/production-drawings.md#115-hard-checks--done-criteria)
- [Spec §11.10: Drawing Intent IR](file:///d:/01_Data/code/sw-mcp/docs/architecture/drawing-intent-ir.md)
- [Spec §11.10.1: Resolved Scheme](file:///d:/01_Data/code/sw-mcp/docs/architecture/drawing-intent-ir.md#11101-dimension-scheme)
- [Spec §6.5.2: Backend Operations](file:///d:/01_Data/code/sw-mcp/docs/architecture/backend-operations.md#652-vocabulary)
- [ADR-031: Drawing Geometry Snapshot](file:///d:/01_Data/code/sw-mcp/docs/adr/ADR-031-drawing-geometry-snapshot.md)
- [ADR-038: Monorepo & ExecutionServer](file:///d:/01_Data/code/sw-mcp/docs/adr/ADR-038-execution-server.md)
- [Guideline G1: C# COM Lifecycle](file:///d:/01_Data/code/sw-mcp/docs/development/implementation-guidelines.md#g1--c-addin-com-object-lifecycle-and-sta-threading)
- [Guideline G2: Python Layering](file:///d:/01_Data/code/sw-mcp/docs/development/implementation-guidelines.md#g2--python-layering-and-the-backend-port)

---

## Global Constraints

- **Clean-room implementation (ADR-010):** Never copy code from SolidPilot. Study observable behavior and failure modes only.
- **Custody of source files (ADR-022):** Never modify source parts or template files in place. Write only to scratch directories (`%TEMP%\sw-mcp-test-live`).
- **Purity and Layering (Guideline G2):** `cad-ir` and `cad-drawing` must perform zero I/O, have no network/clock dependencies, and contain no CAD vendor imports. Enforced by `lint-imports`.
- **C# COM Safety (Guideline G1):** Wrap all COM proxies (`drawingDoc`, `view`, `ann`, `dispDim`, `dim`, etc.) in `try/finally` blocks and release explicitly with `Marshal.ReleaseComObject`. Never call `FinalReleaseComObject`.
- **CAD-free ExecutionServer.Core (ADR-038):** `ExecutionServer.Core` must remain 100% free of SOLIDWORKS references; enforced by `BannedSymbols.txt`.
- **Quantized Units (Spec 3.4.3):** Length quantum is 1e-4 mm, angles 1e-6°, drawing check geometry epsilon 0.01 mm.

---

## Review Focus

1. **Duplicate Dimension Elimination:** When model items are inserted across multiple views (e.g. Front, Top, Right), the same sketch/feature dimension can appear in multiple views. Cleanup must identify duplicate parameters and hide redundant copies (`dimension.hide`) so Check D5 passes with 0 duplicates.
2. **First-Pass Auto-Arrangement:** SOLIDWORKS's native `IModelDocExtension.AlignDimensions((int)swAlignDimensionType_AutoArrange, spacing)` must be invoked on the views with valid default spacing (e.g. 10.0 mm / 0.01 m) so dimension lines don't collide with geometry out of the box.
3. **ISO 128 Center Marks:** Visible cylindrical holes and circular contours must have center marks automatically placed (`AutoInsertCenterMarks2`) without generating duplicate overlapping center marks.
4. **Stable Scheme Identity (Spec 3.4.4):** Derived scheme IDs must be calculated deterministically from `kind`, `covers`, `measures`, and `source`, never from insertion or traversal order.
5. **No Regressions on Geometric Checks:** Hard checks D1 (no crossing), D2 (no text overlap), D3 (no text on model edge), D5 (no duplicates), and D7 (inside sheet border & clear of title block) must all evaluate cleanly on the snapshot.

---

## User Review Required

> [!IMPORTANT]
> **Native Import + Cleanup Strategy (Spec 11.4):**
> Per spec 11.4 (owner decision), dimension placement follows an **import + clean up** workflow rather than generating every dimension from scratch:
> 1. `model_items.insert`: imports dimensions from the model (`MarkedForDrawing` and feature dimensions).
> 2. `center_mark.add`: automatically places center marks on hole features.
> 3. `dimensions.auto_arrange`: invokes SOLIDWORKS native alignment to establish baseline spacing.
> 4. `dimension.hide`: hides duplicates and non-functional dimensions to resolve the dimension scheme.
> 5. Geometry snapshot read-back verifies Checks D1–D3, D5, D7.

---

## Proposed Changes & Tasks

### Task 0: Branch Setup & Synchronization

**Goal:** Sync `main` with GitHub PR #11, switch to `feat/drawing-annotation-pipeline`, and initialize the tracking ledger.

**Files:**
- Modify: `.superpowers/sdd/2026-11-05-drawing-annotation-pipeline/progress.md`
- Create: `docs/superpowers/plans/2026-11-05-drawing-annotation-pipeline.md`

- [ ] **Step 1:** Verify PR #11 status on GitHub, fetch `github/main`, ensure local worktree is clean.
- [ ] **Step 2:** Create and checkout branch `feat/drawing-annotation-pipeline`.
- [ ] **Step 3:** Commit plan document at `docs/superpowers/plans/2026-11-05-drawing-annotation-pipeline.md`.
- [ ] **Step 4:** Initialize tracking ledger at `.superpowers/sdd/2026-11-05-drawing-annotation-pipeline/progress.md`.

---

### Task 1: Contract Schemas & Spec Bump to v1.27

**Goal:** Define normative JSON schemas (Draft 2020-12) for `drawing-intent/v0.json`, `resolved-scheme/v0.json`, and annotation IPC operations (`model_items.insert`, `dimensions.auto_arrange`, `center_mark.add`, `dimension.hide`, `dimension.show`, `dimension.move`), generate C# and Python types, and bump the specification version to v1.27.

**Files:**
- Create: `schemas/drawing-intent/v0.json`
- Create: `schemas/resolved-scheme/v0.json`
- Create: `schemas/ipc/ops/model_items.insert.json`
- Create: `schemas/ipc/ops/dimensions.auto_arrange.json`
- Create: `schemas/ipc/ops/center_mark.add.json`
- Create: `schemas/ipc/ops/dimension.hide.json`
- Create: `schemas/ipc/ops/dimension.show.json`
- Create: `schemas/ipc/ops/dimension.move.json`
- Create: `tests/fixtures/schemas/drawing-intent/valid/minimal.json`
- Create: `tests/fixtures/schemas/drawing-intent/invalid/missing_id.json`
- Create: `tests/fixtures/schemas/drawing-intent/structural/null.json`
- Create: `tests/fixtures/schemas/resolved-scheme/valid/minimal.json`
- Create: `tests/fixtures/schemas/resolved-scheme/invalid/missing_entries.json`
- Create: `tests/fixtures/schemas/resolved-scheme/structural/null.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/model_items.insert.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/dimensions.auto_arrange.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/center_mark.add.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/dimension.hide.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/dimension.show.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/dimension.move.json`
- Modify: `docs/specifications/README.md`
- Modify: `docs/specifications/CHANGELOG.md`
- Modify: All 27 topic files in `docs/` (bump header line to v1.27)

- [ ] **Step 1:** Create `schemas/drawing-intent/v0.json` defining module, id, schema_version, units, documents, configuration, general_tolerance, surface_finish, datums, critical_dimensions, gdt, and scheme_overrides (Spec §11.10).
- [ ] **Step 2:** Create `schemas/resolved-scheme/v0.json` defining entries mapping with kind, covers, measures, source, tolerance, status, auxiliary, and origin (Spec §11.10.1).
- [ ] **Step 3:** Create IPC ops schemas:
  - `model_items.insert.json`: view (optional string), source (`entire_model` | `selected_feature`), types (list of strings e.g. `dimensions_marked`, `dimensions_not_marked`, `hole_callouts`), duplicate_dims (boolean).
  - `dimensions.auto_arrange.json`: view (string), spacing_mm (number, minimum 0).
  - `center_mark.add.json`: view (string), hole_centers (boolean), slot_centers (boolean), size_mm (optional number).
  - `dimension.hide.json`: annotation (string), reason (string).
  - `dimension.show.json`: annotation (string).
  - `dimension.move.json`: annotation (string), position (array of 2 numbers [x, y]), center_text (optional boolean).
- [ ] **Step 4:** Create fixtures in `tests/fixtures/schemas/drawing-intent/`, `tests/fixtures/schemas/resolved-scheme/`, and `tests/fixtures/schemas/ipc/ops/`.
- [ ] **Step 5:** Run `uv run python scripts/generate_contracts.py` to regenerate Python models (`cad_ir.generated.ipc`, `schemas.py`) and C# messages (`Messages.g.cs`).
- [ ] **Step 6:** Bump spec version to v1.27 across all documentation files and log to `CHANGELOG.md`.
- [ ] **Step 7:** Verify contracts pass: `uv run python scripts/generate_contracts.py --check` and `uv run pytest tests/contract/`.
- [ ] **Step 8:** Commit: `feat(spec): add drawing-intent, resolved-scheme, and annotation ops schemas; bump to v1.27`.

---

### Task 2: Drawing Intent IR & Resolved Scheme in Python (`cad-ir`)

**Goal:** Implement typed dataclasses, canonical dictionary conversion, and schema parsing for `DrawingIntent` and `ResolvedScheme` in `cad-ir`.

**Files:**
- Create: `packages/cad-ir/src/cad_ir/drawing_intent/model.py`
- Create: `packages/cad-ir/src/cad_ir/drawing_intent/parse.py`
- Create: `packages/cad-ir/src/cad_ir/drawing_intent/__init__.py`
- Create: `packages/cad-ir/src/cad_ir/resolved_scheme/model.py`
- Create: `packages/cad-ir/src/cad_ir/resolved_scheme/parse.py`
- Create: `packages/cad-ir/src/cad_ir/resolved_scheme/__init__.py`
- Test: `packages/cad-ir/tests/test_drawing_intent.py`
- Test: `packages/cad-ir/tests/test_resolved_scheme.py`

- [ ] **Step 1:** Write failing unit tests in `test_drawing_intent.py` and `test_resolved_scheme.py`.
- [ ] **Step 2:** Implement `DrawingIntent` models:
  - `DrawingIntent`, `SurfaceFinish`, `DatumFeature`, `CriticalDimension`, `Tolerance`, `GDTCallout`, `Context`.
  - `parse_drawing_intent(doc: JsonValue) -> DrawingIntent | IssueReport`.
- [ ] **Step 3:** Implement `ResolvedScheme` models:
  - `ResolvedScheme`, `SchemeEntry`, `ToleranceSpec`.
  - `parse_resolved_scheme(doc: JsonValue) -> ResolvedScheme | IssueReport`.
- [ ] **Step 4:** Run tests: `uv run pytest packages/cad-ir/tests/ -v`.
- [ ] **Step 5:** Run linters & type checker: `uv run ruff check packages/cad-ir/`, `uv run pyright packages/cad-ir/`.
- [ ] **Step 6:** Commit: `feat(cad-ir): implement Drawing Intent and Resolved Scheme IR models and parsing`.

---

### Task 3: Pure Dimension Scheme Resolver & Cleanup Engine (`cad-drawing`)

**Goal:** Implement pure logic in `cad-drawing` to resolve snapshot dimensions into scheme entries, compute stable IDs (Spec 3.4.4), identify duplicate dimensions across views, and map tolerances from `DrawingIntent`.

**Files:**
- Create: `packages/cad-drawing/src/cad_drawing/dimension_scheme/resolver.py`
- Create: `packages/cad-drawing/src/cad_drawing/dimension_scheme/cleanup.py`
- Create: `packages/cad-drawing/src/cad_drawing/dimension_scheme/__init__.py`
- Test: `packages/cad-drawing/tests/test_dimension_scheme.py`

- [ ] **Step 1:** Write failing unit tests in `packages/cad-drawing/tests/test_dimension_scheme.py`.
- [ ] **Step 2:** Implement `compute_scheme_entry_id(kind, covers, measures, source)` using SHA-256 stable hashing (Spec 3.4.4).
- [ ] **Step 3:** Implement `resolve_scheme_from_snapshot(snapshot, intent)`:
  - Extracts dimensions from snapshot views.
  - Matches parameters against intent critical dimensions.
  - Generates `ResolvedScheme` with `shown` entries.
- [ ] **Step 4:** Implement `identify_duplicate_dimensions(scheme, snapshot)`:
  - Detects identical parameter dimensions present in more than one view.
  - Selects the primary view (e.g. Front or view with highest resolution/extents) and marks duplicates as `status: hidden`, `reason: duplicate`.
- [ ] **Step 5:** Run tests: `uv run pytest packages/cad-drawing/tests/test_dimension_scheme.py -v`.
- [ ] **Step 6:** Verify purity with `uv run lint-imports`.
- [ ] **Step 7:** Commit: `feat(cad-drawing): implement pure dimension scheme resolver and duplicate cleanup`.

---

### Task 4: CAD-Free Annotation Placement Math in `ExecutionServer.Core` (C#)

**Goal:** Implement pure mathematical calculations for annotation spacing, clearance, and dimension line bounds in `ExecutionServer.Core`.

**Files:**
- Create: `apps/execution-server/ExecutionServer.Core/Drawings/AnnotationPlacementMath.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/Drawings/AnnotationPlacementMathTests.cs`

- [ ] **Step 1:** Write failing unit tests in `AnnotationPlacementMathTests.cs`.
- [ ] **Step 2:** Implement `AnnotationPlacementMath`:
  - `CalculateDimensionOffset(double baselineMm, int rank, double spacingMm) -> double`.
  - `IsOverlapping(double minX1, double minY1, double maxX1, double maxY1, double minX2, double minY2, double maxX2, double maxY2, double marginMm) -> bool`.
  - `CalculateTextCenter(double[] corners) -> (double x, double y)`.
- [ ] **Step 3:** Run `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`.
- [ ] **Step 4:** Verify BannedSymbols analyzer check passes with zero warnings.
- [ ] **Step 5:** Commit: `feat(core): implement CAD-free AnnotationPlacementMath in ExecutionServer.Core`.

---

### Task 5: SOLIDWORKS Annotation & Dimension Adapters in `ExecutionServer.Adapters` & `SwAddin` (C#)

**Goal:** Implement `AnnotationPlacementAdapter.cs` in `ExecutionServer.Adapters` handling `model_items.insert`, `dimensions.auto_arrange`, `center_mark.add`, `dimension.hide`, `dimension.show`, and `dimension.move` with safe COM release (Guideline G1), and wire into `SwAddin.cs`.

**Files:**
- Create: `apps/execution-server/ExecutionServer.Adapters/Drawings/AnnotationPlacementAdapter.cs`
- Modify: `apps/execution-server/ExecutionServer.AddIn/SwAddin.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/Drawings/AnnotationPlacementAdapterContractTests.cs`

- [ ] **Step 1:** Implement `AnnotationPlacementAdapter.cs`:
  - `InsertModelItems(ModelItemsInsertParams p, CancellationToken ct) -> ModelItemsInsertResult`:
    - Calls `drawingDoc.InsertModelAnnotations3((int)source, typesBitmask, allViews, duplicateDims, false, false)`.
    - Returns count of annotations inserted.
  - `AutoArrangeDimensions(DimensionsAutoArrangeParams p, CancellationToken ct) -> DimensionsAutoArrangeResult`:
    - Selects dimensions in target view or active sheet.
    - Calls `modelDoc.Extension.AlignDimensions((int)swAlignDimensionType_e.swAlignDimensionType_AutoArrange, spacingMeters)`.
  - `AutoInsertCenterMarks(CenterMarkAddParams p, CancellationToken ct) -> CenterMarkAddResult`:
    - Finds view by name.
    - Calls `view.AutoInsertCenterMarks2(insertType, insertOption, linearSlot, arcSlot, useDocDefaults, sizeM, gapM, extended, font, angle)`.
  - `HideDimension(DimensionHideParams p, CancellationToken ct) -> DimensionHideResult`:
    - Finds annotation by name.
    - Sets `ann.Visible = (int)swAnnotationVisibilityState_e.swAnnotationHidden`.
  - `ShowDimension(DimensionShowParams p, CancellationToken ct) -> DimensionShowResult`:
    - Sets `ann.Visible = (int)swAnnotationVisibilityState_e.swAnnotationVisible`.
  - `MoveDimension(DimensionMoveParams p, CancellationToken ct) -> DimensionMoveResult`:
    - Finds annotation and calls `ann.SetPosition2(xM, yM, 0.0)`.
  - Strict COM release of all `IDrawingDoc`, `IView`, `IAnnotation`, `IDisplayDimension`, `IModelDocExtension` proxies in `finally` blocks.
- [ ] **Step 2:** Update `SwAddin.cs`:
  - Register new operations in `HelloResult.Operations`.
  - Dispatch new operations in `DefaultAddinCommandHandler.Execute()`.
- [ ] **Step 3:** Add contract serialization unit tests in `AnnotationPlacementAdapterContractTests.cs`.
- [ ] **Step 4:** Run `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` and `dotnet build apps/execution-server/ExecutionServer.sln`.
- [ ] **Step 5:** Commit: `feat(adapters): implement AnnotationPlacementAdapter and wire annotation ops in SwAddin`.

---

### Task 6: Application Pipeline & Annotation Operations (`cad-application`)

**Goal:** Implement `annotation_ops.py` in `packages/cad-application/` to coordinate model items insertion, auto center marks, dimension scheme cleanup (hiding duplicates), and layout updates.

**Files:**
- Create: `packages/cad-application/src/cad_application/drawing/annotation_ops.py`
- Modify: `packages/cad-application/src/cad_application/drawing/__init__.py`
- Test: `tests/contract/test_annotation_ops.py`

- [ ] **Step 1:** Write failing tests in `tests/contract/test_annotation_ops.py`.
- [ ] **Step 2:** Implement `plan_annotation_insertion_ops(...)`:
  - Produces `model_items.insert` operation.
  - Produces `center_mark.add` operations for orthographic views.
  - Produces `dimensions.auto_arrange` operations for each view.
- [ ] **Step 3:** Implement `plan_dimension_cleanup_ops(...)`:
  - Takes read-back snapshot, derives `ResolvedScheme`, finds duplicates.
  - Produces `dimension.hide` operations for redundant duplicates.
- [ ] **Step 4:** Run `uv run pytest tests/contract/test_annotation_ops.py -v`.
- [ ] **Step 5:** Run `uv run lint-imports` to verify purity and boundary compliance (Guideline G2).
- [ ] **Step 6:** Commit: `feat(application): implement annotation_ops pipeline and cleanup planner`.

---

### Task 7: Live SOLIDWORKS Annotation Pipeline & Hard Checks Validation

**Goal:** Create live integration test `tests/live/test_live_annotation_pipeline.py` exercising end-to-end view creation, model items insertion, auto center marks, auto arrangement, duplicate hiding, and verifying that Checks D1, D2, D3, D5, and D7 pass with 0 violations live in SOLIDWORKS 2025 SP0.1.

**Files:**
- Create: `tests/live/test_live_annotation_pipeline.py`
- Modify: `HANDOFF.md`

- [ ] **Step 1:** Implement `tests/live/test_live_annotation_pipeline.py`:
  - Connect to running SOLIDWORKS 2025 SP0.1 session via `discover_sessions()`.
  - Generate A3 sheet format (`sheet_format.generate`) and create drawing (`drawing.create`).
  - Plan and create standard first-angle views (`plan_ortho_views` + `view.create`).
  - Insert model dimensions (`model_items.insert`).
  - Auto-insert center marks on hole features (`center_mark.add`).
  - Auto-arrange dimensions (`dimensions.auto_arrange`).
  - Take snapshot via `backend.snapshot_drawing()`.
  - Run pure duplicate cleanup (`plan_dimension_cleanup_ops`) and apply `dimension.hide` batch.
  - Re-take snapshot, parse snapshot into `Snapshot` model.
  - Run geometric checks (`run_geometry_checks`):
    - Assert `check_result.status("D1") == "pass"` (0 crossing dimensions).
    - Assert `check_result.status("D2") == "pass"` (0 text overlaps).
    - Assert `check_result.status("D3") == "pass"` (0 text on geometry).
    - Assert `check_result.status("D5") == "pass"` (0 duplicate parameters).
    - Assert `check_result.status("D7") == "pass"` (0 border/title-block violations).
  - Save (`document.save`) and close (`document.close`).
- [ ] **Step 2:** Run `uv run pytest tests/live/test_live_annotation_pipeline.py -m live -v`.
- [ ] **Step 3:** Run complete verification suite:
  - `uv run python scripts/generate_contracts.py --check`
  - `uv run ruff check` and `uv run ruff format --check`
  - `uv run pyright`
  - `uv run lint-imports`
  - `uv run pytest`
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`
  - `dotnet build apps/execution-server/ExecutionServer.sln`
- [ ] **Step 4:** Update `HANDOFF.md` with verified live test evidence and completed milestone details.
- [ ] **Step 5:** Commit: `test(live): verify end-to-end annotation placement and D1-D7 checks in SOLIDWORKS 2025`.

---

## Verification Plan

### Automated Tests
```bash
# Contract schemas & codegen
uv run python scripts/generate_contracts.py --check

# Code formatting & typing
uv run ruff check
uv run ruff format --check
uv run pyright
uv run lint-imports

# Python test suite
uv run pytest tests/contract/test_annotation_ops.py -v
uv run pytest

# C# test suite & solution build
dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj
dotnet build apps/execution-server/ExecutionServer.sln

# Live SOLIDWORKS integration test
uv run pytest tests/live/test_live_annotation_pipeline.py -m live -v
```

### Manual Verification
- In the active SOLIDWORKS 2025 window, confirm:
  1. The drawing sheet contains all 4 standard views.
  2. Model dimensions are inserted and neatly arranged outside the part contours.
  3. Circular holes and slots have clean ISO 128 center marks.
  4. Duplicate dimensions are hidden.
  5. All views and annotations remain cleanly inside the sheet border and clear of the title block.
