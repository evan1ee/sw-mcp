# Handoff

Last updated: 2026-11-05. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Phase:** Phase 1c ("Annotation & Dimension Placement Pipeline: Drawing Intent IR, Pure Dimension Scheme Resolution & Cleanup, Backend Annotation Placement & Hard Checks D1-D7 Validation", Spec §11.4, §11.5, §11.10, §11.10.1, §6.5.2) complete. End-to-end model items insertion, ISO 128 center mark insertion, dimension auto-arrangement, duplicate dimension identification and hiding, and Hard Checks D1, D2, D3, D5, and D7 validated live against local SOLIDWORKS 2025 SP0.1 with 0 violations.
- **Spec:** v1.27 across all 29 topic files in `docs/`. Section 11.10 (Drawing Intent IR) and Section 11.10.1 (Resolved Scheme IR) normative schemas defined. Section 6.5.2 updated for 6 IPC annotation operations: `model_items.insert`, `dimensions.auto_arrange`, `center_mark.add`, `dimension.hide`, `dimension.show`, `dimension.move`. 2 open decisions remain: K3 (title block locators) and J11 (draft-view switched indicator). Catalogue has 40 codes.
- **Branch:** `feat/drawing-annotation-pipeline` (branched from updated `main` after merging PR #11 `feat/drawing-view-pipeline` at `bdedfc3`).
- **Verification Suite Evidence:**
  - `uv run python scripts/generate_contracts.py --check` passes cleanly (0 drift across C# and Python contracts).
  - `uv run ruff check` and `uv run ruff format --check` pass cleanly across all 381 files.
  - `uv run pyright` passes (0 errors, 0 warnings across all packages, apps, tests).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest -m "not live"` passes (2,712 passed, 6 deselected in 38.3s).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (241 passed, 0 failed in 1s).
  - `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings, 0 errors.
  - `uv run pytest tests/live/ -m live -v` passes (5 passed, 1 skipped in 8.7s):
    - `test_live_annotation_pipeline::test_live_annotation_and_dimension_pipeline`: PASSED (model items inserted, center marks added, dimensions auto-arranged, duplicates hidden, D1/D2/D3/D5/D7 pass with 0 failures)
    - `test_live_view_pipeline::test_live_view_planning_and_creation_pipeline`: PASSED (4 views placed, 0 check D7 violations)
    - `test_live_sheet_format::test_live_sheet_format_generate_and_drawing_create`: PASSED
    - `test_live_smoke::test_live_session_discovery`: PASSED
    - `test_live_smoke::test_live_session_handshake`: PASSED
    - `test_live_smoke::test_live_drawing_snapshot`: SKIPPED (standalone snapshot test requiring external file)

## Changes Made

- **Specification & Contracts (Task 1):**
  - Added JSON Schemas (2020-12):
    - `schemas/drawing-intent/v0.json` (Spec §11.10)
    - `schemas/resolved-scheme/v0.json` (Spec §11.10.1)
    - 6 IPC operation schemas in `schemas/ipc/ops/`: `model_items.insert.json`, `dimensions.auto_arrange.json`, `center_mark.add.json`, `dimension.hide.json`, `dimension.show.json`, `dimension.move.json` (Spec §6.5.2)
  - Added valid, invalid, and structural schema fixtures in `tests/fixtures/schemas/`.
  - Regenerated Python models (`cad_ir.generated.ipc`, `schemas.py`) and C# types (`Messages.g.cs`).
  - Bumped specification version to v1.27 across all 29 topic files in `docs/` and added entry to `docs/specifications/CHANGELOG.md`. Committed as `ecfd940`.
- **Drawing Intent & Resolved Scheme IR in `cad-ir` (Task 2):**
  - Implemented `cad_ir.drawing_intent` (`model.py`, `parse.py`, `__init__.py`) providing typed dataclasses for `DrawingIntent`, `IntentContext`, `SurfaceFinish`, `DatumFeature`, `CriticalDimension`, and `GDTCallout`.
  - Implemented `cad_ir.resolved_scheme` (`model.py`, `parse.py`, `__init__.py`) providing typed dataclasses for `ResolvedScheme` and `SchemeEntry`.
  - Added unit tests in `packages/cad-ir/tests/test_drawing_intent.py` and `test_resolved_scheme.py` (7 tests, all passed). Committed as `12afbf6`.
- **Pure Dimension Scheme Resolver & Cleanup in `cad-drawing` (Task 3):**
  - Implemented `cad_drawing.dimension_scheme.resolver` with `resolve_scheme_from_snapshot()` deriving deterministic IDs (`ds_<slug>_<hex>`) via `cad_ir.core.derived_ids.scheme_entry_id` (Spec 3.4.4) and matching critical dimensions from `DrawingIntent`.
  - Implemented `cad_drawing.dimension_scheme.cleanup` with `plan_duplicate_cleanup()` grouping dimensions by model parameter across views, selecting primary views (preferring front/base), and generating `HideAction`s; and `apply_cleanup_to_scheme()` updating `status='hidden'` on redundant entries.
  - Added unit tests in `packages/cad-drawing/tests/test_dimension_scheme.py` (5 tests, all passed). Committed as `a47ee05`.
- **CAD-Free Annotation Placement Math in `ExecutionServer.Core` (Task 4):**
  - Implemented `AnnotationPlacementMath.cs` in `apps/execution-server/ExecutionServer.Core/Drawings/` providing baseline offset calculation (`CalculateDimensionOffset`), AABB overlap detection with clearance margin (`IsOverlapping`), text box centroid math (`CalculateTextCenter`), and unit conversions.
  - Added unit tests in `apps/execution-server/ExecutionServer.Tests/Drawings/AnnotationPlacementMathTests.cs` (38 tests, all passed). Verified zero BannedSymbols violations. Committed as `22e2d0f`.
- **SOLIDWORKS Annotation Adapters in `ExecutionServer.Adapters` & `SwAddin` (Task 5):**
  - Implemented `AnnotationPlacementAdapter.cs` handling:
    - `model_items.insert`: calls `drawingDoc.InsertModelAnnotations3` with specified type bitmasks and sources.
    - `dimensions.auto_arrange`: activates target view and invokes `modelDoc.Extension.AlignDimensions` with `swAlignDimensionType_AutoArrange`.
    - `center_mark.add`: invokes `view.AutoInsertCenterMarks2` for circular holes and slots per ISO 128.
    - `dimension.hide` and `dimension.show`: manages annotation visibility via `swAnnotationVisibilityState_e` without deleting dimensions.
    - `dimension.move`: adjusts dimension position via `ann.SetPosition2`.
    - Strict Guideline G1 COM release (`Marshal.ReleaseComObject` in `finally` blocks) and Spec 8.3 Rule 11 selection by entity.
  - Wired operations into `SwAddin.cs` capability declaration and execution dispatcher.
  - Added contract tests in `AnnotationPlacementAdapterContractTests.cs` (6 tests). Committed as `4035e47`.
- **Application Pipeline in `cad-application` (Task 6):**
  - Implemented `cad_application.drawing.annotation_ops`:
    - `plan_annotation_insertion_ops()`: coordinates `model_items.insert`, `center_mark.add` for orthographic views, and `dimensions.auto_arrange`.
    - `plan_dimension_cleanup_ops()`: runs pure duplicate planning and scheme resolution, producing `dimension.hide` operations for redundant copies.
  - Added contract tests in `tests/contract/test_annotation_ops.py` (2 tests, validated against JSON Schemas). Committed as `5e0911a`.
- **Live SOLIDWORKS Integration & Hard Checks Validation (Task 7):**
  - Implemented `tests/live/test_live_annotation_pipeline.py`: exercises end-to-end sheet format generation, drawing creation, pure view planning, backend view creation in SOLIDWORKS 2025 SP0.1, model items insertion, center mark insertion, auto arrangement, snapshot reading, duplicate cleanup planning, batch duplicate hiding, and evaluation of Checks D1, D2, D3, D5, and D7 (all passing with 0 failures).
  - Fixed pipe transport closure across live tests (`backend.close()` in `finally:` blocks). Committed as `3819c82`.

## Next Steps

1. **Phase 2a: Critical Dimension & Tolerance Verification Pipeline (Spec §11.6, §11.10.1):**
   - Implement Check D4 (tolerance stackup / fit check) and Check D6 (GD&T syntax and datum reference frame validation).
   - Author implementation plan for Phase 2a connecting `DrawingIntent` critical dimensions and GD&T callouts to `ResolvedScheme`.
2. **Open Decisions (K3 & J11):**
   - K3: Inspect standard ISO drawing formats (`standards/iso/templates/`) in SOLIDWORKS to define default zone locators for title-block field read-back.
   - J11: Detect whether a draft-quality view was switched to high quality in snapshot.
3. **Open Pull Request:**
   - Push `feat/drawing-annotation-pipeline` to GitHub remote and open PR against `main`.

## Known Issues

- **K3 remains open:** Reading title-block fields back from owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot does not yet report whether a draft-quality view was switched to high quality; awaiting interactive inspection.
