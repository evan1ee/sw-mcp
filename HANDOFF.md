# Handoff

Last updated: 2026-11-04. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Phase:** Milestone 8 ("Backend Sheet Format Generation & Drawing Document Creation", Spec 11.12, ADR-055, K7) complete. Live execution verified against local SOLIDWORKS 2025 SP0.1.
- **Spec:** v1.25 across all 27 topic files. Section 6.5.2 updated in `docs/architecture/backend-operations.md`. Open decision K7 closed (backend `.slddrt` generation path). 2 open decisions remain: K3 (title block locators) and J11 (draft-view switched indicator). Catalogue has 40 codes.
- **Branch:** `feat/sheet-format-generation` (branched from clean `main` after PR #9 merge).
- **Verification Suite Evidence:**
  - `uv run python scripts/generate_contracts.py --check` passes cleanly (0 drift across C# and Python contracts).
  - `uv run ruff check` and `uv run ruff format --check` pass cleanly across all 355 files.
  - `uv run pyright` passes (0 errors, 0 warnings).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest` passes (2,487 passed, 1 skipped in 43.3s).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (166 passed, 0 failed).
  - `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings, 0 errors.
  - `uv run pytest tests/live/ -m live -v` passes (3 passed, 1 skipped in 4.9s):
    - `test_live_sheet_format_generate_and_drawing_create`: PASSED
    - `test_live_session_discovery`: PASSED
    - `test_live_session_handshake`: PASSED
    - `test_live_drawing_snapshot`: SKIPPED (requires external test drawing path)

## Changes Made

- **Specification & Contracts:**
  - Added JSON Schemas under `schemas/ipc/ops/`: `sheet_format.generate.json`, `drawing.create.json`, `document.save.json`.
  - Added schema test fixtures (valid, invalid, structural) under `tests/fixtures/schemas/ipc/`.
  - Regenerated Python models (`cad_ir.generated.ipc`, `schemas.py`) and C# contracts (`Messages.g.cs`).
  - Closed Open Decision K7 in `docs/specifications/open-decisions.md` and updated `docs/architecture/backend-operations.md` (§6.5.2). Bumped spec to v1.25 with changelog entry.
- **Backend Execution Engine (C#):**
  - Implemented `SheetFormatGeometry.cs` in `ExecutionServer.Core` for pure mathematical calculations of paper sizes, border lines, and title block note links.
  - Implemented `SheetFormatGenerator.cs` in `ExecutionServer.Adapters`: creates temporary drawings, clears default template geometry, draws border/title block lines, inserts text notes and attribute links, renders first-angle projection symbol, and exports `.slddrt` via `ISheet.SaveFormat`.
  - Implemented `DrawingCreationAdapter.cs` in `ExecutionServer.Adapters` handling `drawing.create` (paper sizes, template resolution, `.slddrt` attachment) and `document.save` (`SaveAs4` silent persistence).
  - Updated `DrawingSnapshotAdapter.cs` to resolve active and open drawing documents by title and path.
  - Updated `SwAddin.cs` operation dispatcher to route `sheet_format.generate`, `drawing.create`, and `document.save`, and write UTF-8 session files without BOM (`new UTF8Encoding(false)`).
- **Core Service & Protocols (Python):**
  - Updated `core_service.discovery` to decode session files with `utf-8-sig` (handling .NET UTF-8 BOM) and preserve live sessions during transient read locks.
  - Implemented `mapping_from_drawing_template(template)` in `packages/cad-drawing/src/cad_drawing/checks/d8.py` to map template zone locators to title block fields.
  - Created live integration test `tests/live/test_live_sheet_format.py` exercising sheet format generation, drawing creation, snapshot validation against schema, document saving, and document closing live in SOLIDWORKS 2025.

## Next Steps

1. **Phase 1b Drawing Pipeline Plan:**
   - Author implementation plan for view planning, model insertion, and automated view layout (Spec 11.4).
   - Wire `insert_view` and `arrange_views` operations to connect backend drawing generation with geometry models.
2. **Title Block Locators (K3):**
   - Inspect standard ISO drawing formats (`standards/iso/templates/`) in SOLIDWORKS to define default zone locators for title-block field read-back.
3. **Open Pull Request:**
   - Push `feat/sheet-format-generation` to remote repository and open PR against `main`.

## Known Issues

- **K3 remains open:** Reading title-block fields back from owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot does not yet report whether a draft-quality view was switched to high quality; awaiting interactive inspection.
