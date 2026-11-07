# Handoff

Last updated: 2026-11-07 (branch `feat/sketch-arcs`, spec v1.40).
> **Handoff Rule ([AGENTS.md §5](AGENTS.md#5-session-handoff)):** Keep this file as short as possible. Rewrite in place — **never** append an incremental history (`git log` and [`CHANGELOG.md`](docs/specifications/CHANGELOG.md) record history). Keep only the current state snapshot, the latest session's **Changes Made**, prioritized **Next Steps**, and active **Known Issues**, linking to `docs/` instead of repeating details.

## Current State

- **Active Focus — 3D Part Chain ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [Roadmap §18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)):**
  - **Sketch Arc Primitives (`SK-ENT-013`, `SK-ENT-016`) Implemented End-to-End:** Full support for center-point circular arcs (`Arc(center, start, end, direction)`) across JSON Schemas, code contracts, `cad-ir` models and face reflection, `cad-compiler` semantic validation and lowering, `cad-verification` closed-form profile integration and cylinder expectations, C# `ExecutionServer.Adapters` (`sm.CreateArc`), and `cad-application` authoring guide & eval suite.
  - **Agent IR Authoring:** `get_authoring_guide` MCP tool + 14-case benchmark in [`tests/cad-benchmark/`](tests/cad-benchmark/test_part_ir_benchmark.py) (`14/14` passing: 9 positive builds including `plate_slot`, 5 refusals).
- **2D Drawings — Frozen at `eea9389` ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)):**
  - Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark` until the owner lifts the freeze.
- **Verification Baseline (2026-11-07 on `feat/sketch-arcs`):**
  - Contracts (`generate_contracts.py --check`), `ruff check`, `ruff format --check`, `pyright`, `lint-imports`: **0 errors/drift**.
  - Implementation checklists audit (`check_implementation_checklists.py`): **587 items, 71 capabilities, 0 problems**.
  - Python tests (`pytest --ignore=tests/drawing-benchmark`): **3,462 passed, 38 deselected**.
  - C# tests (`dotnet test apps/execution-server`): **346 passed**; `dotnet build -c Release`: **0 warnings/errors**.
  - Prompt-to-IR benchmark (`scripts/score_part_ir.py`): **14/14 passed**.

## Changes Made

- **Sketch Arc Primitives (`SK-ENT-013`, `SK-ENT-016`, [ADR-071](docs/adr/ADR-071-sketch-arc-primitives.md), Spec v1.40):**
  - **Spec & Schemas:** Added [ADR-071](docs/adr/ADR-071-sketch-arc-primitives.md); updated schemas (`part-feature-graph/v0.json` with `$defs/Arc` and `$defs/SketchEntity`, `ipc/ops/sketch.create.json` with `arc` and direction); regenerated Python and C# contracts; bumped spec to v1.40 across topic files and changelog.
  - **Pure Core IR & Compiler:** Added `Arc` model to `cad-ir`; supported arc reflection and direction inversion on mirrored start faces (`faces.py`); generalized loop closure validation to lines and arcs in `cad-compiler`; lowered `Arc` to `sketch.create` IPC operation.
  - **Verification Engine:** Implemented Green's theorem closed-form arc integration for exact cross-sectional area, bounding box with arc extrema, polygon sampling for centroid, and registered expected cylindrical faces in `cad-verification`.
  - **Execution Server:** Implemented `SketchCreateEntityType.Arc` in `SketchAdapter.cs` dispatching to `sm.CreateArc` with COM cleanup (`Marshal.ReleaseComObject`).
  - **Authoring & Benchmark:** Updated `authoring_guide.py` rules and worked examples; added `plate_slot` benchmark case to `cases.py`, `references.py`, and `part_ir_baseline_answers.json`.
  - **Checklists:** Updated `SK-ENT-013` and `SK-ENT-016` status to `Tested` in `docs/implementation/sketch/sketch-entities.md`.

## Next Steps

1. **Merge `feat/sketch-arcs` to `main`:** All tests pass, zero lint/contract/checklist issues.
2. **Next 3D Part Milestone (pick rows from [checklists](docs/implementation/README.md)):**
   - Fillets and chamfers (`BF-FIL`, `BF-CHM`), sketch corner/center rectangles, or linear/circular patterns.
3. **When Drawing Freeze Lifts ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md)):**
   - Resolve owner decisions O1–O6 and open items K3, K8–K10, J11 in [`open-decisions.md`](docs/specifications/open-decisions.md).

## Known Issues

- **Add-in Debug DLL Lock:** While SOLIDWORKS is open with the Debug add-in loaded, `ExecutionServer.AddIn/bin/x64/Debug/net48` is file-locked; close SOLIDWORKS before `dotnet build -c Debug` (or build `-c Release` / test `ExecutionServer.Tests.csproj`).
- **3D Part Scope Limits:** Side faces (`<node>.side_faces`), edges, cut faces, fillets, chamfers, patterns, and blind cuts measured from the far face are unsupported and refused by validation (K28).
- **Frozen Drawing Caveats ([architecture review F1–F6](docs/superpowers/review/2026-11-05-architecture-review.md)):** Drawing checks D1/D2/D3/D7 currently pass on stubbed border/title-block read-back; run only on scratch copies while frozen.
