# Handoff

Last updated: 2026-11-07 (branch `feat/linear-pattern`, spec v1.43).
> **Handoff Rule ([AGENTS.md §5](AGENTS.md#5-session-handoff)):** Keep this file as short as possible. Rewrite in place — **never** append an incremental history (`git log` and [`CHANGELOG.md`](docs/specifications/CHANGELOG.md) record history). Keep only the current state snapshot, the latest session's **Changes Made**, prioritized **Next Steps**, and active **Known Issues**, linking to `docs/` instead of repeating details.

## Current State

- **Active Focus — 3D Part Chain ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [Roadmap §18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)):**
  - **Linear Feature Pattern (`PAT-LIN-001`..`PAT-LIN-004`) Complete:** Linear pattern feature implemented end-to-end (Spec v1.43, [ADR-074](docs/adr/ADR-074-linear-pattern-feature.md)) with pure core IR lowering, closed-form verification geometry, C# add-in adapters with edge-aligned direction selection, node ID reference resolution, authoring guide rules, and benchmark fixture (`plate_pattern_holes`). Verified live against SOLIDWORKS 2025 (`test_live_linear_pattern_plate`, `test_live_direct_linear_pattern_ops`) and promoted to `Verified`.
  - **Agent IR Authoring:** `get_authoring_guide` MCP tool + 16-case benchmark in [`tests/cad-benchmark/`](tests/cad-benchmark/test_part_ir_benchmark.py) (`16/16` passing with `plate_pattern_holes`, 11 positive builds, 5 refusals).
- **2D Drawings — Frozen at `eea9389` ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)):**
  - Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark` until the owner lifts the freeze.
- **Verification Baseline (2026-11-07 on `feat/linear-pattern`):**
  - Contracts (`generate_contracts.py --check`), `ruff check`, `ruff format --check`, `pyright`, `lint-imports`: **0 errors/drift**.
  - Implementation checklists audit (`check_implementation_checklists.py`): **587 items, 71 capabilities, 0 problems** (`patterns-mirrors.md` has 4 verified items; total verified items = 54).
  - Python tests (`pytest --ignore=tests/drawing-benchmark`): **3,518 passed, 44 deselected**.
  - Live SOLIDWORKS 2025 tests (`pytest tests/live/test_live_part_chain.py -m live`): **25 passed, 1 skipped cleanly** (including `test_live_linear_pattern_plate`, `test_live_direct_linear_pattern_ops`).
  - C# tests (`dotnet test apps/execution-server`): **351 passed**; `dotnet build -c Release` & `-c Debug`: **0 warnings/errors**.
  - Prompt-to-IR benchmark (`scripts/score_part_ir.py`): **16/16 passed**.

## Changes Made

- **Linear Feature Pattern (`PAT-LIN-001`..`PAT-LIN-004`, [ADR-074](docs/adr/ADR-074-linear-pattern-feature.md), Spec v1.43):**
  - **Spec & Schemas:** Added [ADR-074](docs/adr/ADR-074-linear-pattern-feature.md); added `schemas/part-feature-graph/features/linear_pattern.json`; updated `part-feature-graph/v0.json` with `LinearPattern` and `LinearPatternDirection`; updated `ipc/ops/feature.create.json` with `linear_pattern` type and fields (`direction_1`, `direction_2`, `seeds`); regenerated Python and C# contracts; bumped spec to v1.43 across 35 files.
  - **Pure Core IR & Compiler:** Added `LinearPatternDirection` and `LinearPattern` models in `cad-ir`; added semantic validation (seeds, direction, spacing > 0, count >= 2) in `cad-compiler`; implemented lowering to `feature.create` operation in `lower.py`.
  - **Verification Engine:** Implemented closed-form expected geometry (volume accounting for replicated hole seeds, cylinder count) in `cad-verification/part.py`; updated contract tests for `native_type="LPattern"`.
  - **Execution Server:** Implemented `LinearPattern` in `FeatureAdapter.cs` using pre-selection Mark 4 for seed features, Mark 1/2 for linear direction edges via `FindDirectionEdge` with ComScope tracking and orientation dot product reverse detection; unit tests in `LinearPatternParamTests.cs`.
  - **Authoring & Benchmark:** Updated `authoring_guide.py` with `linear_pattern` syntax and examples; added `plate_pattern_holes` to `cases.py`, `references.py`, and `part_ir_baseline_answers.json` (`16/16` scored passing).
  - **Live SOLIDWORKS Verification & Promotion:** Added `test_live_linear_pattern_plate` and `test_live_direct_linear_pattern_ops` in `tests/live/test_live_part_chain.py`; resolved node IDs to feature IDs in `plan_job.py`; verified against live SOLIDWORKS 2025; promoted `PAT-LIN-001` through `PAT-LIN-004` to `Verified` in `patterns-mirrors.md`.

## Next Steps

1. **Commit, Push, PR & Merge `feat/linear-pattern`:**
   - Commit Task 6 changes, push to origin, open PR, and merge into `main`.
2. **Next 3D Part Milestone (pick from [checklists](docs/implementation/README.md)):**
   - **Circular Feature Pattern (`PAT-CIR-001`..`005`):** Implement circular pattern feature around a reference axis or cylindrical face.
   - **Semantic Edge References & Fillets/Chamfers (`BF-FIL`, `BF-CHM`, K23/K28):** Draft ADR and grammar for persistent semantic edge references required by constant-radius fillets and chamfers.
3. **When Drawing Freeze Lifts ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md)):**
   - Resolve owner decisions O1–O6 and open items K3, K8–K10, J11 in [`open-decisions.md`](docs/specifications/open-decisions.md).

## Known Issues

- **Add-in DLL Lock:** While SOLIDWORKS is running with the add-in loaded, `sw-mcp.AddIn.dll` is file-locked; close SOLIDWORKS before rebuilding or re-registering.
- **3D Part Scope Limits:** Side faces (`<node>.side_faces`), edges, cut faces, fillets, chamfers, circular patterns, and blind cuts measured from the far face are unsupported and refused by validation (K28).
- **Frozen Drawing Caveats ([architecture review F1–F6](docs/superpowers/review/2026-11-05-architecture-review.md)):** Drawing checks D1/D2/D3/D7 currently pass on stubbed border/title-block read-back; run only on scratch copies while frozen.
