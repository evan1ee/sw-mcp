# Handoff

Last updated: 2026-11-07 (branch `feat/sketch-straight-slot`, spec v1.42).
> **Handoff Rule ([AGENTS.md §5](AGENTS.md#5-session-handoff)):** Keep this file as short as possible. Rewrite in place — **never** append an incremental history (`git log` and [`CHANGELOG.md`](docs/specifications/CHANGELOG.md) record history). Keep only the current state snapshot, the latest session's **Changes Made**, prioritized **Next Steps**, and active **Known Issues**, linking to `docs/` instead of repeating details.

## Current State

- **Active Focus — 3D Part Chain ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [Roadmap §18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)):**
  - **Sketch Straight Slot Primitives (`SK-ENT-021`) Complete:** Straight slot primitive implemented end-to-end (Spec v1.42, [ADR-073](docs/adr/ADR-073-sketch-straight-slot-primitive.md)) with CCW line and arc lowering, closed-form verification geometry, C# add-in adapters with COM cleanup, authoring guide rules, and benchmark fixture adaptation. Verified live against SOLIDWORKS 2025 (`test_live_direct_slot_ops`, `test_live_slot_plate`) and promoted to `Verified`.
  - **Agent IR Authoring:** `get_authoring_guide` MCP tool + 15-case benchmark in [`tests/cad-benchmark/`](tests/cad-benchmark/test_part_ir_benchmark.py) (`15/15` passing with native `straight_slot` `plate_slot` fixture, 10 positive builds, 5 refusals).
- **2D Drawings — Frozen at `eea9389` ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)):**
  - Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark` until the owner lifts the freeze.
- **Verification Baseline (2026-11-07 on `feat/sketch-straight-slot`):**
  - Contracts (`generate_contracts.py --check`), `ruff check`, `ruff format --check`, `pyright`, `lint-imports`: **0 errors/drift**.
  - Implementation checklists audit (`check_implementation_checklists.py`): **587 items, 71 capabilities, 0 problems**.
  - Python tests (`pytest --ignore=tests/drawing-benchmark`): **3,479 passed, 41 deselected**.
  - Live SOLIDWORKS 2025 tests (`pytest tests/live -m live`): **35 passed, 7 skipped cleanly** (including `test_live_slot_plate`, `test_live_direct_slot_ops`, `test_live_rectangle_plate`, `test_live_direct_rectangle_ops`).
  - C# tests (`dotnet test apps/execution-server`): **346 passed**; `dotnet build -c Release` & `-c Debug`: **0 warnings/errors**.
  - Prompt-to-IR benchmark (`scripts/score_part_ir.py`): **15/15 passed**.

## Changes Made

- **Sketch Straight Slot Primitives (`SK-ENT-021`, [ADR-073](docs/adr/ADR-073-sketch-straight-slot-primitive.md), Spec v1.42):**
  - **Spec & Schemas:** Added [ADR-073](docs/adr/ADR-073-sketch-straight-slot-primitive.md); updated schemas (`part-feature-graph/v0.json` with `$defs/StraightSlot` and union `SketchEntity`; `ipc/ops/sketch.create.json` with `straight_slot`, `start_point`, `end_point`); regenerated Python and C# contracts; bumped spec to v1.42 across 32 topic files, `docs/README.md`, `docs/specifications/README.md`, and changelog.
  - **Pure Core IR & Compiler:** Added `StraightSlot` dataclass to `cad-ir`; supported start-face coordinate reflection in `faces.py`; added dimension and loop closure validation in `cad-compiler`; implemented deterministic CCW lowering into 2 parallel lines and 2 semicircular arcs in `lower.py`.
  - **Verification Engine:** Implemented closed-form expected geometry (area, bounding box, perimeter, center of mass, cylinder diameters) for straight slots in `cad-verification/part.py`; updated `_sketch_entity_count` in `contracts.py` (4 lowered segments per slot).
  - **Execution Server:** Implemented `SketchCreateEntityType.StraightSlot` in `SketchAdapter.cs` with COM cleanup (`Marshal.ReleaseComObject`) via `CreateLineSegment` and `CreateArcSegment`.
  - **Authoring & Benchmark:** Updated `authoring_guide.py` rules and worked examples for `straight_slot`; adapted `references.py` and `part_ir_baseline_answers.json` `plate_slot` fixture to native `straight_slot` (`15/15` scored passing).
  - **Live SOLIDWORKS Verification & Checklists:** Added `test_live_direct_slot_ops` in `tests/live/test_live_part_chain.py` (both `test_live_slot_plate` and `test_live_direct_slot_ops` passed against live SOLIDWORKS 2025); promoted `SK-ENT-021` to `Verified` in `docs/implementation/sketch/sketch-entities.md`.

## Next Steps

1. **Merge `feat/sketch-straight-slot`:**
   - Review diff, open PR, and merge into `main`.
2. **Next 3D Part Milestone (pick rows from [checklists](docs/implementation/README.md)):**
   - **Feature Patterns (`PAT-LIN`, `PAT-CIR`):** Implement linear pattern (`PAT-LIN`) or circular pattern (`PAT-CIR`) on solid features (e.g. patterning hole cuts across a plate).
   - **Semantic Edge References & Fillets/Chamfers (`BF-FIL`, `BF-CHM`, K23/K28):** Draft ADR and grammar for persistent semantic edge references required by constant-radius fillets and chamfers.
3. **When Drawing Freeze Lifts ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md)):**
   - Resolve owner decisions O1–O6 and open items K3, K8–K10, J11 in [`open-decisions.md`](docs/specifications/open-decisions.md).

## Known Issues

- **Add-in DLL Lock:** While SOLIDWORKS is running with the add-in loaded, `sw-mcp.AddIn.dll` is file-locked; close SOLIDWORKS before rebuilding or re-registering.
- **3D Part Scope Limits:** Side faces (`<node>.side_faces`), edges, cut faces, fillets, chamfers, patterns, and blind cuts measured from the far face are unsupported and refused by validation (K28).
- **Frozen Drawing Caveats ([architecture review F1–F6](docs/superpowers/review/2026-11-05-architecture-review.md)):** Drawing checks D1/D2/D3/D7 currently pass on stubbed border/title-block read-back; run only on scratch copies while frozen.
