# Milestone 8: Backend Sheet Format Generation & Drawing Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement backend `.slddrt` sheet format generation (`sheet_format.generate`), drawing document creation (`drawing.create`), and document save (`document.save`) in the C# execution server and Python layers, resolving Open Decision K7 to bridge Drawing Template IR (§11.12, ADR-055) into real SOLIDWORKS 2025 drawing production.

**Architecture:**
- **Schema & Contract (`schemas/ipc/ops/`):** Define JSON Schemas for `sheet_format.generate.json`, `drawing.create.json`, and `document.save.json`. Generate typed Python dataclasses and C# classes via `scripts/generate_contracts.py`.
- **C# Sheet Format Generator (`ExecutionServer.Adapters`):** Translate Drawing Template IR (paper size, margins, title-block zones, dividing lines, static notes, property-linked notes `$PRPSHEET`/`$PRP`, and first-angle projection symbol geometry) into SOLIDWORKS drawing sheet format entities inside `IDrawingDoc.EditTemplate()`, saving the resulting format via `IDrawingDoc.SaveSheetFormat()`.
- **C# Drawing Operations (`ExecutionServer.Adapters` & `ExecutionServer.AddIn`):** Handle `drawing.create` (instantiating new drawings with the generated `.slddrt` or default template) and `document.save` (safe export/drawing persistence per ADR-046). Adhere strictly to COM safety (Guideline G1) and UI-thread synchronization (§8.6.2).
- **Python Integration & D8 Linkage (`cad-application`, `cad-drawing`):** Dispatch `sheet_format.generate` and `drawing.create` through `Backend.apply_ops()`. Resolve template field locators so drawing check D8 validates generated drawings without requiring external TOML mappings.
- **Verification:** Unit and contract tests in C# and Python; live verification against the active interactive SOLIDWORKS 2025 session.

**Tech Stack:**
- C# .NET Framework 4.8, SOLIDWORKS 2025 Interop assemblies (`SolidWorks.Interop.sldworks`, `SolidWorks.Interop.swconst`), Newtonsoft.Json
- Python 3.13 (`cad-ir`, `cad-application`, `cad-drawing`, `core-service`), pytest, pytest-cov
- JSON Schema Draft 2020-12

**Spec:**
- §6.5.2 (Backend Operation Vocabulary: Sheet format, Drawing structure, Document groups)
- §11.12 (Drawing Template IR)
- §11.5.3 (Drawing Check D8 and title-block field validation)
- ADR-046 (Document ownership, save and output policy)
- ADR-055 (IR-generated sheet formats alongside owner-supplied formats)
- Open Decision K7 (Sheet format generation path from Drawing Template IR)

---

## Global Constraints

- **IR-First Architecture (Spec 1.3, ADR-054):** All sheet formats, margins, text positions, and attribute links originate from structured IR data, never by reverse-engineering or hacking binary CAD files.
- **Clean-Room Implementation (ADR-010):** No code from the reference implementation (SolidPilot). Rely exclusively on official SOLIDWORKS API contracts and specified IR schemas.
- **Custody of Source Files (ADR-022):** Never modify source parts or vaulted drawings without permission. All test drawings and sheet formats operate on scratch paths under `%TEMP%` or test output folders.
- **Python Layering & Purity (Guideline G2):** Pure packages (`cad-ir`, `cad-drawing`) perform zero I/O and contain no vendor imports. All CAD interactions occur through `Backend` ports.
- **C# COM Safety (Guideline G1):** Wrap all COM interfaces (`ISldWorks`, `IModelDoc2`, `IDrawingDoc`, `ISheet`, `INote`, `IAnnotation`) in `try/finally` blocks with explicit `Marshal.ReleaseComObject`. Never call `Marshal.FinalReleaseComObject`.
- **Zero Completion Claims Without Verification (Spec 4):** All code changes must be verified with clean runs of `generate_contracts.py --check`, `ruff`, `pyright`, `lint-imports`, `dotnet test`, `dotnet build`, and live smoke tests.

---

## Review Focus

1. **Sheet Format Edit Mode Isolation:** Ensure `IDrawingDoc.EditTemplate()` is always paired with `IDrawingDoc.EditSheet()` in a `finally` block so the drawing document is never left in an un-editable sheet format edit mode.
2. **Linked Note Property Syntax:** SOLIDWORKS evaluates model custom properties only with `$PRPSHEET:"<PropName>"` and drawing properties with `$PRP:"<PropName>"`. Verify exact escaping so quotes do not break string interpolation or JSON serialization.
3. **Projection Symbol Geometry Scaling:** Ensure first-angle projection symbol geometry fits within its allocated bounding box (`box` in `fields.projection_symbol`) and scales predictably based on standard paper dimensions.
4. **Temporary Document Lifecycle:** Temporary drawing documents created during sheet format generation must be closed with `sw.CloseDoc` without prompting the user to save, preventing memory leaks or lingering UI locks.
5. **D8 Locator Resolution on Generated Sheets:** Verify that drawing check D8 correctly identifies attribute link notes on generated sheet formats using the template IR's bounding boxes without triggering `title_block_mapping_missing`.

---

## Tasks

### Task 0: Conclude Live Execution Gate & Sync Main

**Goal:** Record the successful live drawing snapshot verification in `HANDOFF.md`, merge `feat/live-execution-gate` to `main`, and create feature branch `feat/sheet-format-generation`.

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1:** Update `HANDOFF.md` to record that `test_live_drawing_snapshot` ran and passed live against SOLIDWORKS 2025 SP0.1 with `dissectiontemplate.slddrw`.
- [ ] **Step 2:** Commit changes on `feat/live-execution-gate` and push to GitHub.
- [ ] **Step 3:** Merge `feat/live-execution-gate` into `main`.
- [ ] **Step 4:** Create and switch to new branch `feat/sheet-format-generation`.

---

### Task 1: Contract Schemas for `sheet_format.generate`, `drawing.create`, and `document.save`

**Goal:** Author JSON Schemas for the new backend operations, update normative docs, close Open Decision K7, and generate Python/C# contract types.

**Files:**
- Create: `schemas/ipc/ops/sheet_format.generate.json`
- Create: `schemas/ipc/ops/drawing.create.json`
- Create: `schemas/ipc/ops/document.save.json`
- Modify: `docs/specifications/open-decisions.md` (record K7 as resolved and closed)
- Modify: `docs/architecture/backend-operations.md` (§6.5.2)
- Modify: `docs/specifications/CHANGELOG.md`
- Generated: `packages/cad-ir/src/cad_ir/generated/ipc.py`
- Generated: `apps/execution-server/ExecutionServer.Core/Ipc/Generated/`

**Interfaces:**
- `sheet_format.generate`:
  - `params`: `{ "template": object (DrawingTemplate IR), "destination_path": string, "_meta"?: Meta }`
  - `result`: `{ "path": string, "size_mm": [number, number] }`
  - `mutates`: `"none"`
  - `errors`: `["IR_SCHEMA_INVALID", "AUTH_PATH_DENIED", "BACKEND_BUSY", "BACKEND_UI_BLOCKED"]`
- `drawing.create`:
  - `params`: `{ "destination_path"?: string, "sheet_format_path"?: string, "template_path"?: string, "paper_size"?: string, "width_mm"?: number, "height_mm"?: number, "_meta"?: Meta }`
  - `result`: `{ "document": string, "sheet_name": string }`
  - `mutates`: `"document"`
- `document.save`:
  - `params`: `{ "path": string, "target_path"?: string, "_meta"?: Meta }`
  - `result`: `{ "saved_path": string }`
  - `mutates`: `"document"`

- [ ] **Step 1:** Create `schemas/ipc/ops/sheet_format.generate.json`, `schemas/ipc/ops/drawing.create.json`, and `schemas/ipc/ops/document.save.json`.
- [ ] **Step 2:** Update `docs/specifications/open-decisions.md` marking K7 closed with reference to the generation architecture.
- [ ] **Step 3:** Update `docs/architecture/backend-operations.md` §6.5.2 and bump changelog in `docs/specifications/CHANGELOG.md`.
- [ ] **Step 4:** Run `uv run python scripts/generate_contracts.py`.
- [ ] **Step 5:** Verify with `uv run python scripts/generate_contracts.py --check`.

---

### Task 2: C# Sheet Format Generator (`ExecutionServer.Adapters`)

**Goal:** Implement `SheetFormatGenerator` in C# to draw borders, zones, divider lines, notes, linked fields, and the projection symbol in SOLIDWORKS drawing sheet format mode, then save `.slddrt`.

**Files:**
- Create: `apps/execution-server/ExecutionServer.Adapters/Drawings/SheetFormatGenerator.cs`
- Create: `apps/execution-server/ExecutionServer.Tests/Drawings/SheetFormatGeneratorTests.cs`

**Interfaces:**
- Consumes: `ISldWorks`, Drawing Template JSON (`JObject`), output path (`string`)
- Produces: `SheetFormatGenerationResult { string Path, double WidthMm, double HeightMm }`

- [ ] **Step 1: Write C# unit tests** for parameter validation, margin geometry calculations, and note text link formatting (`$PRPSHEET` vs `$PRP`).
- [ ] **Step 2: Implement `SheetFormatGenerator.cs`**:
  - `GenerateSheetFormat(ISldWorks sw, JObject template, string destinationPath, CancellationToken ct)`
  - Call `sw.INewDocument2("", (int)swDwgPaperSizes_e.swDwgPapersUserDefined, widthM, heightM)` to create temp drawing.
  - Call `drawingDoc.EditTemplate()`.
  - Draw border rectangle using `modelDoc.CreateLine2(x1, y1, 0, x2, y2, 0)`.
  - Draw title block lines from `title_block.lines`.
  - Insert static notes from `texts` using `modelDoc.Extension.InsertAnnotation` / note creation with text height and alignment.
  - Insert attribute link notes from `fields` formatting `$PRPSHEET:"<name>"` or `$PRP:"<name>"`.
  - Draw ISO first-angle projection symbol geometry if projection field exists.
  - Save via `drawingDoc.SaveSheetFormat(destinationPath)`.
  - Exit template mode via `drawingDoc.EditSheet()`, close temporary drawing via `sw.CloseDoc`.
  - Strictly wrap in `try/finally` with `Marshal.ReleaseComObject` per Guideline G1.
- [ ] **Step 3:** Run `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` and `dotnet build apps/execution-server/ExecutionServer.sln`.

---

### Task 3: C# Drawing Creation & Document Save Handlers

**Goal:** Implement `drawing.create` and `document.save` in `ExecutionServer.Adapters` and wire all three operations into `SwAddin.cs` operation dispatcher.

**Files:**
- Create: `apps/execution-server/ExecutionServer.Adapters/Drawings/DrawingCreationAdapter.cs`
- Modify: `apps/execution-server/ExecutionServer.AddIn/SwAddin.cs`
- Create: `apps/execution-server/ExecutionServer.Tests/Drawings/DrawingCreationAdapterTests.cs`

**Interfaces:**
- `DrawingCreationAdapter.CreateDrawing(ISldWorks sw, DrawingCreateParams p, CancellationToken ct)`: Creates drawing, applies sheet format via `ISheet.SetSheetFormatName` or `ReloadTemplate`, returns document title and active sheet.
- `DrawingCreationAdapter.SaveDocument(ISldWorks sw, DocumentSaveParams p, CancellationToken ct)`: Saves document to path via `IModelDoc2.SaveAs3`.

- [ ] **Step 1: Write unit tests** for `DrawingCreationAdapter` parameter checks and path resolution.
- [ ] **Step 2: Implement `DrawingCreationAdapter.cs`** with COM safety and parameter handling.
- [ ] **Step 3: Update `SwAddin.cs`** `ExecuteSingleOp` to dispatch `sheet_format.generate`, `drawing.create`, and `document.save` to their respective adapters.
- [ ] **Step 4: Verify C# build and tests:** `dotnet test` and `dotnet build`.

---

### Task 4: Python Service Integration & Check D8 Support

**Goal:** Wire the operations into `cad-application` and update drawing check D8 to evaluate title-block fields on drawings with generated sheet formats.

**Files:**
- Modify: `packages/cad-application/src/cad_application/tools/` (or drawing service)
- Modify: `packages/cad-drawing/src/cad_drawing/checks/d8_title_block.py`
- Create: `packages/cad-drawing/tests/test_d8_template_locators.py`

- [ ] **Step 1: Write unit test** in `cad-drawing` verifying that check D8 resolves fields using `DrawingTemplate` IR zone locators.
- [ ] **Step 2: Update `d8_title_block.py`** to extract expected field names and bounds from `DrawingTemplate` when present in drawing context.
- [ ] **Step 3: Verify Python suite:** `uv run pytest packages/cad-drawing` and full checks (`ruff`, `pyright`, `lint-imports`).

---

### Task 5: Live SOLIDWORKS 2025 Verification

**Goal:** Execute live integration test against running SOLIDWORKS 2025 instance validating end-to-end sheet format generation, drawing creation, snapshot extraction, and clean teardown.

**Files:**
- Create: `tests/live/test_live_sheet_format.py`

- [ ] **Step 1: Implement live test:**
  - Connect to live session via `discover_sessions()` and `NamedPipeBackendProvider`.
  - Dispatch `sheet_format.generate` with `minimal.json` template IR, target `%TEMP%\test_format.slddrt`.
  - Assert `%TEMP%\test_format.slddrt` exists and is non-empty.
  - Dispatch `drawing.create` using the generated sheet format.
  - Dispatch `drawing.snapshot` to read back geometry and annotations.
  - Assert snapshot validates against schema and contains expected sheet dimensions and title block zones.
  - Dispatch `document.close` (save=False) and remove scratch files.
- [ ] **Step 2: Run live test:** `uv run pytest tests/live/test_live_sheet_format.py -v`.
- [ ] **Step 3: Run full verification suite:**
  - `uv run python scripts/generate_contracts.py --check`
  - `uv run ruff check`
  - `uv run ruff format --check`
  - `uv run pyright`
  - `uv run lint-imports`
  - `uv run pytest`
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`
  - `dotnet build apps/execution-server/ExecutionServer.sln`
- [ ] **Step 4: Update `HANDOFF.md`** with Milestone 8 completion and results.

---

## Verification Plan

### Automated Tests
1. **Contract generator check:**
   ```bash
   uv run python scripts/generate_contracts.py --check
   ```
2. **Python linting & type checks:**
   ```bash
   uv run ruff check
   uv run ruff format --check
   uv run pyright
   uv run lint-imports
   ```
3. **C# Unit & Contract Tests:**
   ```bash
   dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj
   dotnet build apps/execution-server/ExecutionServer.sln
   ```
4. **Full Python Test Suite:**
   ```bash
   uv run pytest
   ```
5. **Live SOLIDWORKS 2025 Suite:**
   ```bash
   uv run pytest tests/live/test_live_smoke.py tests/live/test_live_sheet_format.py -v
   ```

### Manual Verification
- Verify generated `.slddrt` file can be opened directly or applied to a new drawing in SOLIDWORKS with visible border, title block lines, notes, and first-angle projection symbol.
- Confirm `%LOCALAPPDATA%\sw-mcp\addin-load.log` shows clean operation execution without COM exceptions.
