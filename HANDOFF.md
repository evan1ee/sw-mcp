# Handoff

Last updated: 2026-11-07 (branch `main`, spec v1.41, PR #19 merged).
> **Handoff Rule ([AGENTS.md §5](AGENTS.md#5-session-handoff)):** Keep this file as short as possible. Rewrite in place — **never** append an incremental history (`git log` and [`CHANGELOG.md`](docs/specifications/CHANGELOG.md) record history). Keep only the current state snapshot, the latest session's **Changes Made**, prioritized **Next Steps**, and active **Known Issues**, linking to `docs/` instead of repeating details.

## Current State

- **Active Focus — 3D Part Chain ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [Roadmap §18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)):**
  - **Sketch Rectangle Primitives (`SK-ENT-005`, `SK-ENT-006`) & Arc Verification (`SK-ENT-013`, `SK-ENT-016`) Complete:** Corner and Center Rectangle primitives implemented end-to-end (Spec v1.41, ADR-072) with CCW line lowering, verification geometry, and C# add-in adapters. Both Rectangle primitives and Arc primitives verified live against SOLIDWORKS 2025 and promoted to `Verified`.
  - **Agent IR Authoring:** `get_authoring_guide` MCP tool + 15-case benchmark in [`tests/cad-benchmark/`](tests/cad-benchmark/test_part_ir_benchmark.py) (`15/15` passing: 10 positive builds including `plate_slot` and `plate_rectangles`, 5 refusals).
- **2D Drawings — Frozen at `eea9389` ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)):**
  - Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark` until the owner lifts the freeze.
- **Verification Baseline (2026-11-07 on `feat/sketch-rectangles`):**
  - Contracts (`generate_contracts.py --check`), `ruff check`, `ruff format --check`, `pyright`, `lint-imports`: **0 errors/drift**.
  - Implementation checklists audit (`check_implementation_checklists.py`): **587 items, 71 capabilities, 0 problems**.
  - Python tests (`pytest --ignore=tests/drawing-benchmark`): **3,479 passed, 41 deselected**.
  - Live SOLIDWORKS 2025 tests (`pytest tests/live -m live`): **34 passed, 7 skipped cleanly** (including `test_live_slot_plate`, `test_live_rectangle_plate`, `test_live_direct_rectangle_ops`).
  - C# tests (`dotnet test apps/execution-server`): **346 passed**; `dotnet build -c Release`: **0 warnings/errors**.
  - Prompt-to-IR benchmark (`scripts/score_part_ir.py`): **15/15 passed**.

## Changes Made

- **Sketch Rectangle Primitives (`SK-ENT-005`, `SK-ENT-006`, [ADR-072](docs/adr/ADR-072-sketch-rectangle-primitives.md), Spec v1.41) & Live Arc Verification (`SK-ENT-013`, `SK-ENT-016`):**
  - **Spec & Schemas:** Added [ADR-072](docs/adr/ADR-072-sketch-rectangle-primitives.md); updated schemas (`part-feature-graph/v0.json` with `$defs/CornerRectangle`, `$defs/CenterRectangle`, and union `SketchEntity`; `ipc/ops/sketch.create.json` with `corner_rectangle` and `center_rectangle`); regenerated Python and C# contracts; bumped spec to v1.41 across topic files and changelog.
  - **Pure Core IR & Compiler:** Added `CornerRectangle` and `CenterRectangle` dataclasses to `cad-ir`; supported face plane reflection in `faces.py`; added dimension and loop closure validation in `cad-compiler`; implemented deterministic CCW lowering to 4 `Line` entities in `lower.py`.
  - **Verification Engine:** Implemented expected geometry (area, bounding box, perimeter, center of mass) for rectangle base profiles and cutout regions in `cad-verification/part.py`; updated `_sketch_entity_count` in `contracts.py` so contract verification correctly evaluates lowered rectangle segment counts.
  - **Execution Server:** Implemented `SketchCreateEntityType.CornerRectangle` and `SketchCreateEntityType.CenterRectangle` in `SketchAdapter.cs` with COM cleanup (`Marshal.ReleaseComObject`) for each line segment.
  - **Authoring & Benchmark:** Updated `authoring_guide.py` rules and worked examples; added `plate_rectangles` benchmark case to `cases.py`, `references.py`, and `part_ir_baseline_answers.json` (`15/15` scored passing).
  - **Live SOLIDWORKS Verification & Checklists:** Added `test_live_slot_plate`, `test_live_rectangle_plate`, and `test_live_direct_rectangle_ops` in `tests/live/test_live_part_chain.py` (all passed against live SOLIDWORKS 2025); promoted `SK-ENT-005`, `SK-ENT-006`, `SK-ENT-013`, and `SK-ENT-016` to `Verified` in `docs/implementation/sketch/sketch-entities.md`.

## Next Steps

1. **Merge `feat/sketch-rectangles`:**
   - Review diff, open PR, and fast-forward merge into `main`.
2. **Next 3D Part Milestone (pick rows from [checklists](docs/implementation/README.md)):**
   - **Straight Slots (`SK-ENT-021`):** Build on Arc and Rectangle primitives to implement straight slots across schema, compiler, verification, execution, and authoring.
   - **Patterns (`PAT-LIN`, `PAT-CIR`):** Feature patterns for bolt hole patterns on plates.
   - **Semantic Edge References (K23/K28):** Resolve open decisions K23 and K28 to enable edge fillets ([`BF-FIL`](docs/implementation/part-features/base-features.md)) and chamfers ([`BF-CHM`](docs/implementation/part-features/base-features.md)).
3. **When Drawing Freeze Lifts ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md)):**
   - Resolve owner decisions O1–O6 and open items K3, K8–K10, J11 in [`open-decisions.md`](docs/specifications/open-decisions.md).

## Known Issues

- **Add-in Debug DLL Lock:** While SOLIDWORKS is open with the Debug add-in loaded, `ExecutionServer.AddIn/bin/x64/Debug/net48` is file-locked; close SOLIDWORKS before `dotnet build -c Debug` (or build `-c Release` / test `ExecutionServer.Tests.csproj`).
- **3D Part Scope Limits:** Side faces (`<node>.side_faces`), edges, cut faces, fillets, chamfers, patterns, and blind cuts measured from the far face are unsupported and refused by validation (K28).
- **Frozen Drawing Caveats ([architecture review F1–F6](docs/superpowers/review/2026-11-05-architecture-review.md)):** Drawing checks D1/D2/D3/D7 currently pass on stubbed border/title-block read-back; run only on scratch copies while frozen.
