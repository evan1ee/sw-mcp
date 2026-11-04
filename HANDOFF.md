# Handoff

Last updated: 2026-11-04. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Phase:** Phase 1b ("Drawing View Pipeline: Layout IR, Pure View Planning, Backend View Creation & D7 Validation", Spec §11.4, §11.11, §6.5.2) complete. End-to-end view planning, backend creation, snapshot capture, and Check D7 verification validated live against local SOLIDWORKS 2025 SP0.1 with 0 violations.
- **Spec:** v1.26 across all 27 topic files. Section 11.11 normative schema defined. Section 6.5.2 operations updated for `view.create` and `view.update`. 2 open decisions remain: K3 (title block locators) and J11 (draft-view switched indicator). Catalogue has 40 codes.
- **Branch:** `feat/drawing-view-pipeline` (branched from clean `main` after merging PR #10 `feat/sheet-format-generation` at `2950ad1`).
- **Verification Suite Evidence:**
  - `uv run python scripts/generate_contracts.py --check` passes cleanly (0 drift across C# and Python contracts).
  - `uv run ruff check` and `uv run ruff format --check` pass cleanly across all 366 files.
  - `uv run pyright` passes (0 errors, 0 warnings across all packages, apps, tests).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest` passes (2,581 passed, 1 skipped in 43.7s).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (197 passed, 0 failed).
  - `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings, 0 errors.
  - `uv run pytest tests/live/ -m live -v` passes (4 passed, 1 skipped in 5.3s):
    - `test_live_sheet_format_generate_and_drawing_create`: PASSED
    - `test_live_view_pipeline::test_live_view_planning_and_creation_pipeline`: PASSED (4 views placed, 0 check D7 violations)
    - `test_live_session_discovery`: PASSED
    - `test_live_session_handshake`: PASSED
    - `test_live_drawing_snapshot`: SKIPPED (standalone snapshot test requiring external file)

## Changes Made

- **Specification & Contracts:**
  - Added JSON Schemas: `schemas/drawing-layout/v0.json` (Spec §11.11), `schemas/ipc/ops/view.create.json`, `schemas/ipc/ops/view.update.json` (Spec §6.5.2), and shared `ViewOutline` in `schemas/ipc/v0.json`.
  - Added schema test fixtures (valid, invalid, structural) under `tests/fixtures/schemas/drawing-layout/` and `tests/fixtures/schemas/ipc/`.
  - Regenerated Python models (`cad_ir.generated.ipc`, `schemas.py`) and C# contracts (`Messages.g.cs`).
  - Bumped specification version to v1.26 across all 27 topic files in `docs/` and added `docs/specifications/CHANGELOG.md` entry.
- **Drawing Layout IR in Python (`cad-ir`):**
  - Implemented `cad_ir.drawing_layout` (`model.py`, `parse.py`, `__init__.py`) providing typed dataclasses for `DrawingLayout`, `DrawingSheet`, `DrawingView`, `ViewDisplay`, and `DrawingAnnotation`.
  - Added 4 unit tests in `packages/cad-ir/tests/test_drawing_layout.py` verifying dataclass instantiation, dict roundtrip, and schema validation.
- **Pure View Planning Engine (`cad-drawing`):**
  - Implemented `cad_drawing.view_planning.scales` with ISO 5455 preferred scales table and scale selection algorithm (`select_iso_scale`).
  - Implemented `cad_drawing.view_planning.planner` (`plan_ortho_views`) enforcing ISO 5456-2 first-angle layout: Front view as primary reference, Top view below Front, Right view to left of Front, Isometric view in clear upper quadrant, respecting title block and border margins (D7).
  - Added 8 unit tests in `packages/cad-drawing/tests/test_view_planning.py`.
- **Backend Execution Engine (C#):**
  - Implemented CAD-free `ViewLayoutGeometry.cs` in `ExecutionServer.Core` for millimeter/meter coordinate conversions, ISO scale string parsing, and boundary checks.
  - Added unit tests in `apps/execution-server/ExecutionServer.Tests/Drawings/ViewLayoutGeometryTests.cs`.
  - Implemented `ViewCreationAdapter.cs` in `ExecutionServer.Adapters`: creates views via `IDrawingDoc.CreateDrawViewFromModelView3()`, configures scale (`ScaleDecimal`), configuration (`ReferencedConfiguration`), display mode (HLR), and position, and reads back bounding outlines (`GetOutline()`), adhering strictly to Guideline G1 (`Marshal.ReleaseComObject` in `finally` blocks).
  - Wired `view.create` and `view.update` into `SwAddin.cs` capability declaration and operation dispatcher.
  - Added contract tests in `apps/execution-server/ExecutionServer.Tests/Drawings/ViewCreationAdapterContractTests.cs`.
- **Application Pipeline (`cad-application`):**
  - Implemented `cad_application.drawing.layout_ops`:
    - `layout_to_create_ops()`: maps planned `DrawingLayout` into ordered, schema-compliant `view.create` operations.
    - `derive_as_built_layout()`: updates layout model with measured bounding outlines and centers read back from drawing geometry snapshots.
  - Added contract tests in `tests/contract/test_view_layout_ops.py`.
- **Live Integration & Verification:**
  - Implemented `tests/live/test_live_view_pipeline.py`: exercises end-to-end sheet format generation, drawing creation, pure view planning, backend view creation in SOLIDWORKS 2025, snapshot validation against schema, Check D7 evaluation (asserting 0 violations), as-built layout derivation, document save, and document close.

## Next Steps

1. **Phase 1c Annotation & Dimension Placement Pipeline:**
   - Author implementation plan for annotation placement (dimensions, center marks, datums, surface finish) per Spec §11.5, §11.10.
   - Connect reference resolution and projection raycasting to drawing views.
2. **Open Decisions (K3 & J11):**
   - K3: Inspect standard ISO drawing formats (`standards/iso/templates/`) in SOLIDWORKS to define default zone locators for title-block field read-back.
   - J11: Detect whether a draft-quality view was switched to high quality in snapshot.
3. **Open Pull Request:**
   - Push `feat/drawing-view-pipeline` to GitHub remote and open PR against `main`.

## Known Issues

- **K3 remains open:** Reading title-block fields back from owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot does not yet report whether a draft-quality view was switched to high quality; awaiting interactive inspection.
