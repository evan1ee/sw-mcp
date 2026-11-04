# Phase 1b Drawing View Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1b Drawing View Pipeline (Spec §11.4, §11.11, §6.5.2), including Drawing Layout IR schemas, pure view planning (ISO 5456-2 first-angle projection, ISO 5455 preferred scales, title-block avoidance), backend view creation and positioning operations (`view.create`, `view.update`), and live verification against SOLIDWORKS 2025 ensuring all views pass hard check D7 ("Inside sheet").

**Architecture:**
- **Contracts (`schemas/`):** Author JSON Schemas for `schemas/drawing-layout/v0.json` (Drawing Layout IR: sheets, views, scales, positions, orientations, modifiers), `schemas/ipc/ops/view.create.json`, and `schemas/ipc/ops/view.update.json`. Regenerate Python dataclasses and C# contract types via `scripts/generate_contracts.py`.
- **Pure Core Python (`cad-ir`, `cad-drawing`):** Implement Drawing Layout IR models in `cad_ir.drawing_layout` with canonical serialization (RFC 8785). Implement pure view planning in `cad_drawing.view_planning`: given part extents and sheet dimensions, selects optimal ISO 5455 scale, places standard 3-view orthogonal projection (Front, Top, Right in ISO 5456-2 first-angle) and Isometric view while strictly avoiding title-block and border exclusion zones.
- **Backend Execution Engine (C#):** Implement CAD-free `ViewLayoutGeometry.cs` in `ExecutionServer.Core` for coordinate conversions and boundary math. Implement `ViewCreationAdapter.cs` in `ExecutionServer.Adapters` using `IDrawingDoc.CreateDrawViewFromModelView3()`, setting view scale, referenced configuration, display mode (HLR per ISO 128), and position, with strict Guideline G1 COM release. Route operations in `SwAddin.cs`.
- **Core Service & Application (`cad-application`):** Implement `layout_to_ops` translating planned `DrawingLayout` into `view.create` operations. Derive as-built `DrawingLayout` from `backend.snapshot_drawing()`, confirming 100% compliance with hard check D7.
- **Verification:** Unit tests in Python and C# (CAD-free), schema contract tests, and live integration tests in SOLIDWORKS 2025 SP0.1.

**Tech Stack:**
- C# .NET Framework 4.8, SOLIDWORKS 2025 Interop (`SolidWorks.Interop.sldworks`, `SolidWorks.Interop.swconst`), Newtonsoft.Json
- Python 3.13 (`cad-ir`, `cad-drawing`, `cad-application`, `core-service`), pytest
- JSON Schema Draft 2020-12, RFC 8785 canonical JSON

**Spec References:**
- §6.5.2 (Backend Operation Vocabulary: Drawing structure group — `view.create`, `view.update`)
- §11.2 (Drawing Standards: ISO 5456-2 first-angle, ISO 5455 preferred scales, ISO 128 view display)
- §11.4 (Drawing Pipeline: View planning, view insertion, and model items)
- §11.5.1 & §11.5.3 (Drawing Geometry Snapshot and Hard Check D7 — Inside sheet)
- §11.11 (Drawing Layout IR: sheets, views, orientations, positions, scales, modifiers)
- ADR-046 (Document ownership, save and output policy)

---

## Global Constraints

- **IR-First Architecture (Spec 1.3):** View positions, scales, and orientations originate in the Drawing Layout IR, with deterministic generation before any CAD backend execution.
- **Clean-Room Implementation (ADR-010):** Never copy code from SolidPilot. Implement clean-room adapters based purely on the documented SOLIDWORKS API and specification requirements.
- **Custody of Source Files (ADR-022):** Never modify source parts or template files. Work only in test scratch paths or temporary drawings.
- **Python Layering & Purity (Guideline G2):** `cad-ir` and `cad-drawing` must remain strictly pure: zero I/O, no network or clock dependencies, and no CAD vendor imports.
- **C# COM Safety (Guideline G1):** Wrap every SOLIDWORKS COM pointer (`ISldWorks`, `IModelDoc2`, `IDrawingDoc`, `ISheet`, `IView`) in `try/finally` blocks with `Marshal.ReleaseComObject`. Never call `Marshal.FinalReleaseComObject`.
- **ExecutionServer.Core CAD-Free (ADR-038):** No SOLIDWORKS references in `ExecutionServer.Core`.
- **Zero Completion Claims Without Verification (Spec 4):** No task is complete without passing all linters, type checks, import checks, unit tests, and live tests.

---

## Review Focus

1. **First-Angle vs Third-Angle Orthogonal Arrangement:** In ISO 5456-2 first-angle projection, the Top view (view from above) is projected *below* the Front view, and the Right view (view from the right) is projected to the *left* of the Front view. Verify that view planning places coordinates accordingly.
2. **Title-Block & Border Exclusion (Check D7):** Views must never overlap the sheet border margins (e.g. 20mm left, 10mm others) or the title-block area (typically bottom-right, e.g. 180mm x 65mm on A3). Verify that view planning scales down or shifts views to guarantee D7 passes.
3. **ISO 5455 Scale Quantization:** Scales must strictly adhere to ISO preferred scales (e.g. 1:1, 1:2, 1:5, 1:10, 2:1, 5:1). The planner must pick the largest preferred scale that fits without arbitrary fractional scaling (such as 1:3.7).
4. **Drawing View Metric Units:** SOLIDWORKS COM methods (`CreateDrawViewFromModelView3`, `view.Position`) accept coordinates in meters, while Drawing Layout IR and snapshot use millimeters. Verify all coordinate transformations are exact and quantized.
5. **COM Object Cleanup on View Enumeration:** View creation and snapshot read-back iterate over sheet views. Ensure every returned COM interface is explicitly released in `finally` blocks to avoid orphaned locks.

---

## Tasks

### Task 0: Branch Setup & Milestone 8 Merge

**Goal:** Merge `feat/sheet-format-generation` to `main`, push to remote, and create feature branch `feat/drawing-view-pipeline`.

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1:** Verify git status is clean and all tests currently pass.
- [ ] **Step 2:** Merge `feat/sheet-format-generation` into `main` and push to remote repository.
- [ ] **Step 3:** Create and switch to new branch `feat/drawing-view-pipeline`.
- [ ] **Step 4:** Verify workspace clean state on new branch.

---

### Task 1: Contract Schemas for `drawing-layout` IR, `view.create`, and `view.update`

**Goal:** Author JSON Schemas for Drawing Layout IR (`schemas/drawing-layout/v0.json`), backend operations `schemas/ipc/ops/view.create.json` and `schemas/ipc/ops/view.update.json`, create test fixtures, bump spec version to v1.26, and regenerate C# and Python contracts.

**Files:**
- Create: `schemas/drawing-layout/v0.json`
- Create: `schemas/ipc/ops/view.create.json`
- Create: `schemas/ipc/ops/view.update.json`
- Create: `tests/fixtures/schemas/drawing-layout/valid/minimal.json`
- Create: `tests/fixtures/schemas/drawing-layout/valid/three_view_a3.json`
- Create: `tests/fixtures/schemas/drawing-layout/invalid/missing_sheet.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/view_create_minimal.json`
- Create: `tests/fixtures/schemas/ipc/ops/valid/view_update_minimal.json`
- Modify: `docs/architecture/drawing-layout-ir.md`
- Modify: `docs/architecture/backend-operations.md` (§6.5.2)
- Modify: `docs/specifications/README.md` (bump to v1.26)
- Modify: `docs/specifications/CHANGELOG.md`
- Generated: `packages/cad-ir/src/cad_ir/generated/ipc.py`
- Generated: `packages/cad-ir/src/cad_ir/generated/schemas.py`
- Generated: `apps/execution-server/ExecutionServer.Core/Ipc/Generated/Messages.g.cs`

**Interfaces:**
- `schemas/drawing-layout/v0.json`:
  - `module`: `"drawing_layout"`
  - `id`: string
  - `schema_version`: `"0.1"`
  - `units`: `"mm"`
  - `intent`: string (DocumentRef)
  - `part_path`: string (optional, model path)
  - `sheets`: mapping of sheet ID to `{ size, orientation, scale, sheet_format?, template? }`
  - `views`: mapping of view ID to `{ sheet, type, orientation, configuration?, scale, position: [x, y], display: { hidden_lines: bool, tangent_edges: string }, parent?, modifiers? }`
- `schemas/ipc/ops/view.create.json`:
  - `op`: `"view.create"`
  - `params`: `{ model_path: string, view_type: string, orientation: string, position: [x, y], scale: number, configuration?: string, display_mode?: string, tangent_edges?: string, view_name?: string }`
  - `result`: `{ view_id: string, native_id: string, position_mm: [x, y], scale: number, outline_mm: { min: [x, y], max: [x, y] }, width_mm: number, height_mm: number }`
  - `mutates`: `"document"`
- `schemas/ipc/ops/view.update.json`:
  - `op`: `"view.update"`
  - `params`: `{ view_name: string, position?: [x, y], scale?: number, display_mode?: string }`
  - `result`: `{ native_id: string, position_mm: [x, y], outline_mm: { min: [x, y], max: [x, y] } }`
  - `mutates`: `"document"`

- [ ] **Step 1:** Create `schemas/drawing-layout/v0.json` matching Spec §11.11.
- [ ] **Step 2:** Create `schemas/ipc/ops/view.create.json` and `schemas/ipc/ops/view.update.json` matching Spec §6.5.2.
- [ ] **Step 3:** Add valid and invalid fixtures under `tests/fixtures/schemas/drawing-layout/` and `tests/fixtures/schemas/ipc/ops/`.
- [ ] **Step 4:** Run `uv run python scripts/generate_contracts.py` to update Python and C# contracts.
- [ ] **Step 5:** Run `uv run python scripts/generate_contracts.py --check` and `uv run pytest tests/contract/test_schema_fixtures.py` to confirm zero drift.
- [ ] **Step 6:** Commit: `feat(spec): add drawing-layout and view operations schemas and bump to v1.26`.

---

### Task 2: Drawing Layout IR Model in Python (`packages/cad-ir`)

**Goal:** Implement pure Python data models, parsing, validation, and RFC 8785 canonical serialization for Drawing Layout IR in `packages/cad-ir/src/cad_ir/drawing_layout/`.

**Files:**
- Create: `packages/cad-ir/src/cad_ir/drawing_layout/__init__.py`
- Create: `packages/cad-ir/src/cad_ir/drawing_layout/model.py`
- Create: `packages/cad-ir/src/cad_ir/drawing_layout/parse.py`
- Test: `tests/cad-ir/test_drawing_layout_ir.py`

**Interfaces:**
- Consumes: `cad_ir.core.canonical.canonical_json`, `cad_ir.core.schema_validation.validate_against_schema`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class DrawingView:
      sheet: str
      type: str  # "base", "projected", "isometric", etc.
      orientation: str  # "front", "top", "right", "isometric"
      position: tuple[float, float]  # [x, y] in mm
      scale: str  # "1:1", "1:2", etc.
      configuration: str = "Default"
      display: ViewDisplay = field(default_factory=ViewDisplay)
      parent: str | None = None


  @dataclass(frozen=True)
  class DrawingLayout:
      id: str
      schema_version: str
      intent: str
      sheets: dict[str, DrawingSheet]
      views: dict[str, DrawingView]
      units: str = "mm"
      part_path: str | None = None
  ```

- [ ] **Step 1:** Write failing unit tests in `tests/cad-ir/test_drawing_layout_ir.py` for parsing, serialization, and roundtrip verification of Drawing Layout fixtures.
- [ ] **Step 2:** Run `uv run pytest tests/cad-ir/test_drawing_layout_ir.py -v` and verify failure.
- [ ] **Step 3:** Implement `model.py` and `parse.py` in `packages/cad-ir/src/cad_ir/drawing_layout/`.
- [ ] **Step 4:** Run tests and verify all pass.
- [ ] **Step 5:** Commit: `feat(cad-ir): implement Drawing Layout IR models and parsing`.

---

### Task 3: Pure View Planning & Layout Engine (`packages/cad-drawing`)

**Goal:** Implement the pure view planning algorithm in `cad_drawing.view_planning`: given 3D bounding box extents and sheet parameters, selects the optimal ISO 5455 preferred scale and arranges standard views (Front, Top, Right, Isometric) per ISO 5456-2 first-angle projection, strictly avoiding borders and title-block exclusion zones.

**Files:**
- Create: `packages/cad-drawing/src/cad_drawing/view_planning/__init__.py`
- Create: `packages/cad-drawing/src/cad_drawing/view_planning/scales.py`
- Create: `packages/cad-drawing/src/cad_drawing/view_planning/planner.py`
- Test: `tests/cad-drawing/test_view_planning.py`

**Interfaces:**
- Consumes: `cad_ir.drawing_layout.model.DrawingLayout`, `cad_ir.drawing_layout.model.DrawingView`.
- Produces:
  ```python
  def select_iso_scale(
      part_width_mm: float,
      part_height_mm: float,
      part_depth_mm: float,
      usable_width_mm: float,
      usable_height_mm: float,
      spacing_mm: float = 25.0,
  ) -> tuple[int, int]:
      """Selects the largest ISO 5455 preferred scale (numerator, denominator) that fits."""


  def plan_ortho_views(
      part_extents: tuple[float, float, float],  # (dx, dy, dz)
      sheet_size: str = "A3",
      sheet_width_mm: float = 420.0,
      sheet_height_mm: float = 297.0,
      title_block_box: tuple[float, float, float, float] = (240.0, 0.0, 420.0, 65.0),
      include_isometric: bool = True,
      intent_ref: str = "drawing_intent:PART-001@1",
  ) -> DrawingLayout:
      """Produces a planned DrawingLayout with Front, Top, Right, and Isometric views in ISO first-angle."""
  ```

- [ ] **Step 1:** Write failing tests in `tests/cad-drawing/test_view_planning.py` testing:
  - ISO preferred scale selection across diverse aspect ratios (small bracket, cube, slender shaft, large plate).
  - First-angle alignment: Top view Y < Front view Y; Right view X < Front view X.
  - Title block avoidance: no view intersects `title_block_box`.
  - Sheet margin adherence: no view closer than 10mm to sheet edges.
- [ ] **Step 2:** Run `uv run pytest tests/cad-drawing/test_view_planning.py -v` and verify failure.
- [ ] **Step 3:** Implement `scales.py` (ISO 5455 scale tables and fitting logic) and `planner.py` (first-angle arrangement, spacing, and centering).
- [ ] **Step 4:** Run tests and verify all pass.
- [ ] **Step 5:** Commit: `feat(cad-drawing): implement pure view planning and scale selection`.

---

### Task 4: C# Layout Geometry Math & Calculations (`ExecutionServer.Core`)

**Goal:** Implement CAD-free coordinate conversion and view boundary calculations in `ExecutionServer.Core.Drawings`.

**Files:**
- Create: `apps/execution-server/ExecutionServer.Core/Drawings/ViewLayoutGeometry.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/ViewLayoutGeometryTests.cs`

**Interfaces:**
- Produces:
  ```csharp
  namespace ExecutionServer.Core.Drawings;

  public static class ViewLayoutGeometry
  {
      public static (double xMeters, double yMeters) MmToMeters(double xMm, double yMm);
      public static (double xMm, double yMm) MetersToMm(double xM, double yM);
      public static double ParseScaleRatio(string scale);
      public static bool IsWithinSheet(double minX, double minY, double maxX, double maxY, double sheetW, double sheetH, double marginMm);
  }
  ```

- [ ] **Step 1:** Write failing tests in `ViewLayoutGeometryTests.cs`.
- [ ] **Step 2:** Run `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` and verify failure.
- [ ] **Step 3:** Implement `ViewLayoutGeometry.cs` in `ExecutionServer.Core`.
- [ ] **Step 4:** Run `dotnet test` and verify all tests pass.
- [ ] **Step 5:** Verify BannedSymbols analyzer check passes with zero warnings.
- [ ] **Step 6:** Commit: `feat(core): implement CAD-free ViewLayoutGeometry in ExecutionServer.Core`.

---

### Task 5: C# SOLIDWORKS View Creation & Update Adapters (`ExecutionServer.Adapters`)

**Goal:** Implement `ViewCreationAdapter.cs` in `ExecutionServer.Adapters`, handling `view.create` and `view.update` with safe COM release (Guideline G1), and wire into `SwAddin.cs`.

**Files:**
- Create: `apps/execution-server/ExecutionServer.Adapters/Drawings/ViewCreationAdapter.cs`
- Modify: `apps/execution-server/ExecutionServer.AddIn/SwAddin.cs`
- Test: `apps/execution-server/ExecutionServer.Tests/ViewCreationAdapterContractTests.cs`

**Interfaces:**
- `ViewCreationAdapter`:
  - `CreateView(ViewCreateParams p, CancellationToken ct) -> ViewCreateResult`
    - Uses `drawingDoc.CreateDrawViewFromModelView3(p.ModelPath, viewName, xM, yM, 0.0)`.
    - Configures scale (`view.ScaleDecimal = p.Scale`), configuration (`view.ReferencedConfiguration`), display mode (`swDisplayMode_e`), tangent edges.
    - Sets position (`view.Position = new double[] { xM, yM }`).
    - Reads back outline `(double[])view.GetOutline()` in mm.
    - Safe COM cleanup with `Marshal.ReleaseComObject` in `finally`.
  - `UpdateView(ViewUpdateParams p, CancellationToken ct) -> ViewUpdateResult`
    - Finds view on active sheet, updates position/scale, rebuilds.
- `SwAddin`:
  - Declare `view.create` and `view.update` in `HelloResult.Operations`.
  - Dispatch in `Execute()`.

- [ ] **Step 1:** Implement `ViewCreationAdapter.cs` adhering strictly to Guideline G1.
- [ ] **Step 2:** Update `SwAddin.cs` to register and dispatch `view.create` and `view.update`.
- [ ] **Step 3:** Add contract serialization unit tests for parameter parsing and result generation.
- [ ] **Step 4:** Run `dotnet test` and `dotnet build` to verify 0 warnings and 0 errors.
- [ ] **Step 5:** Commit: `feat(adapters): implement ViewCreationAdapter and wire view ops in SwAddin`.

---

### Task 6: Application Pipeline & Layout Operations (`cad-application`)

**Goal:** Implement `layout_to_ops` in `packages/cad-application/` to transform planned `DrawingLayout` into `view.create` backend operations and derive as-built layouts from snapshots.

**Files:**
- Create: `packages/cad-application/src/cad_application/drawing/layout_ops.py`
- Test: `tests/contract/test_view_layout_ops.py`

**Interfaces:**
- Produces:
  ```python
  def layout_to_create_ops(
      layout: DrawingLayout,
      model_path: str,
      job_prefix: str,
  ) -> list[Operation]:
      """Converts a planned DrawingLayout into an ordered list of view.create operations."""


  def derive_as_built_layout(
      snapshot: dict[str, JsonValue],
      planned_layout: DrawingLayout,
  ) -> DrawingLayout:
      """Derives the as-built DrawingLayout from the read-back snapshot geometry."""
  ```

- [ ] **Step 1:** Write failing tests in `tests/contract/test_view_layout_ops.py`.
- [ ] **Step 2:** Implement `layout_to_ops.py` in `packages/cad-application/src/cad_application/drawing/`.
- [ ] **Step 3:** Run `uv run pytest tests/contract/test_view_layout_ops.py -v` and verify pass.
- [ ] **Step 4:** Run `uv run lint-imports` to verify purity and layer boundary compliance (Guideline G2).
- [ ] **Step 5:** Commit: `feat(application): implement layout_to_ops and as-built layout derivation`.

---

### Task 7: Live SOLIDWORKS View Creation & D7 Validation

**Goal:** Create live integration test `tests/live/test_live_view_pipeline.py` exercising sheet format generation, drawing creation, view planning, backend view creation, snapshot validation, and check D7 verification against local SOLIDWORKS 2025.

**Files:**
- Create: `tests/live/test_live_view_pipeline.py`
- Modify: `HANDOFF.md`

- [ ] **Step 1:** Implement `tests/live/test_live_view_pipeline.py`:
  - Discover active session in `%LOCALAPPDATA%\sw-mcp\sessions`.
  - Generate an A3 sheet format (`sheet_format.generate`) and create drawing (`drawing.create`).
  - Use a test part model (e.g. create or open a 100mm x 50mm x 30mm bracket model).
  - Plan views via `plan_ortho_views()`.
  - Dispatch `view.create` batch via `backend.apply_ops()`.
  - Read back `backend.snapshot_drawing()`.
  - Assert 4 views exist with valid outlines.
  - Run `check_d7(snapshot)` from `cad_drawing.checks.d7` and assert 0 boundary/title-block violations!
  - Save (`document.save`) and close (`document.close`).
- [ ] **Step 2:** Run `uv run pytest tests/live/test_live_view_pipeline.py -m live -v` against SOLIDWORKS 2025 SP0.1.
- [ ] **Step 3:** Run full verification suite:
  - `uv run python scripts/generate_contracts.py --check`
  - `uv run ruff check` and `uv run ruff format --check`
  - `uv run pyright`
  - `uv run lint-imports`
  - `uv run pytest`
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`
  - `dotnet build apps/execution-server/ExecutionServer.sln`
- [ ] **Step 4:** Update `HANDOFF.md` with verified live test evidence and completed milestone details.
- [ ] **Step 5:** Commit: `test(live): verify end-to-end drawing view planning and creation in SOLIDWORKS 2025`.

---

## Verification Plan

### Automated Tests
```bash
# Contract generation check
uv run python scripts/generate_contracts.py --check

# Python code quality & typing
uv run ruff check
uv run ruff format --check
uv run pyright
uv run lint-imports

# Unit & contract tests
uv run pytest
dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj
dotnet build apps/execution-server/ExecutionServer.sln

# Live SOLIDWORKS integration test
uv run pytest tests/live/test_live_view_pipeline.py -m live -v
```

### Manual Verification
- Verify in active SOLIDWORKS 2025 window: the newly created drawing displays the standard first-angle 3-view arrangement (Front, Top below Front, Right to left of Front) and Isometric view cleanly centered inside the A3 drawing sheet, clear of the border and title block.
