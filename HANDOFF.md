# Handoff

Last updated: 2026-11-07 (`main`, spec v1.38).
> **Handoff Rule ([AGENTS.md §5](AGENTS.md#5-session-handoff)):** Keep this file as short as possible. Rewrite in place — **never** append an incremental history (`git log` and [`CHANGELOG.md`](docs/specifications/CHANGELOG.md) record history). Keep only the current state snapshot, the latest session's **Changes Made**, prioritized **Next Steps**, and active **Known Issues**, linking to `docs/` instead of repeating details.

## Current State

- **Active Focus — 3D Part Chain ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [Roadmap §18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)):**
  - **Part Chain MVP + Post-MVP Tech-Debt Cleanup Complete on `main`:** End-to-end MCP-to-`.SLDPRT` pipeline supports `sketch` (lines, circles, rectangles), boss `extrude`, and `cut_extrude` (`blind` / `through_all`) on standard datum planes (`plane:front`, `plane:top`, `plane:right`) and extrude cap faces (`<extrude>.start_face`, `<extrude>.end_face` per [ADR-070](docs/adr/ADR-070-sketch-on-extrude-cap-face.md) & [§5.7.4](docs/architecture/feature-schema-guide.md#574-sketches)).
  - **Agent IR Authoring:** `get_authoring_guide` MCP tool + 13-case benchmark in [`tests/cad-benchmark/`](tests/cad-benchmark/test_part_ir_benchmark.py) (`13/13` passing: 8 positive builds, 5 refusals).
  - **Architecture Reference (spec v1.35+, awaiting owner sign-off):** Proposed [§22 IR](docs/specifications/ir-specification.md), [§23 Compiler](docs/specifications/compiler-architecture-specification.md), and ADR-065..069; open decisions tracked in [`open-decisions.md`](docs/specifications/open-decisions.md).
- **2D Drawings — Frozen at `eea9389` ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)):**
  - Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark` until the owner lifts the freeze.
- **Verification Baseline (2026-11-07 on `main`):**
  - Contracts (`generate_contracts.py`), `ruff`, `pyright`, `lint-imports`: **0 errors/drift**.
  - Python tests (`pytest --ignore=tests/drawing-benchmark`): **3,411 passed**.
  - C# tests (`dotnet test apps/execution-server`): **346 passed**; `dotnet build -c Release`: **0 warnings/errors**.
  - Prompt-to-IR benchmark (`scripts/score_part_ir.py`): **13/13 passed**.
  - Live SOLIDWORKS 2025 (`pytest tests/live/test_live_part_chain.py -m live`): **19 passed, 1 skipped** (`105.7s`).

## Changes Made

- **Clear Post-MVP 3D Part Tech Debt (PR #16, spec v1.38, [plan](docs/superpowers/plans/2026-11-07-clear-part-mvp-tech-debt.md)):**
  - **K29 Closed (Datum-Plane Generalization):** Generalized `<extrude>.start_face` and `<extrude>.end_face` frames, signatures, lowering, and verification across `plane:front`, `plane:top`, and `plane:right` in [`faces.py`](packages/cad-ir/src/cad_ir/part_feature_graph/faces.py), [`cap_faces.py`](packages/cad-geometry/src/cad_geometry/cap_faces.py), [`cap_face_signatures.py`](packages/cad-references/src/cad_references/cap_face_signatures.py), [`part.py` (compiler)](packages/cad-compiler/src/cad_compiler/part.py), [`part.py` (verification)](packages/cad-verification/src/cad_verification/part.py), and [`FaceSignatureTests.cs`](apps/execution-server/ExecutionServer.Tests/Parts/FaceSignatureTests.cs).
  - **Live 3D Part Coverage:** Added `test_blind_hole_in_start_face`, parameterized `test_blind_hole_across_datum_and_cap_faces` (all 6 datum × cap combinations with off-center holes), and `test_block_centre_hole` in [`test_live_part_chain.py`](tests/live/test_live_part_chain.py).
  - **Prompt-to-IR Baseline:** Added `blind_hole_start_face` case, recorded [`part_ir_baseline_answers.json`](tests/cad-benchmark/part_ir_baseline_answers.json), and added [`test_part_ir_benchmark.py`](tests/cad-benchmark/test_part_ir_benchmark.py).
  - **COM & Contract Hygiene:** Scoped COM pointers via `ComScope`, closed untitled `.SLDPRT` handles on `SaveAs4` failure, mapped `COMException` on feature creation/rebuild to `BACKEND_REBUILD_ERROR` in [`ExecutionServer.Adapters/Parts/`](apps/execution-server/ExecutionServer.Adapters/Parts/), and rejected `bool`-for-`int`/`float` in [`contracts.py`](packages/cad-verification/src/cad_verification/api/contracts.py).

## Next Steps

1. **Owner Decision on Next 3D Part Milestone ([Roadmap §18](docs/specifications/roadmap.md)):**
   - Expand 3D Part IR feature coverage (arcs, fillets, chamfers, linear/circular patterns, or side-face references `<node>.side_faces` under K23/K26/K28) via new spec + ADR before implementation.
2. **When Drawing Freeze Lifts ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md), [roadmap](docs/superpowers/review/2026-11-05-architecture-roadmap.md)):**
   - Resolve owner decisions O1–O6 and open items K3, K8–K10, J11 in [`open-decisions.md`](docs/specifications/open-decisions.md), then execute milestones M0–M11 (document custody, real geometry read-back, `not_evaluated` guards, and `produce_drawing`).

## Known Issues

- **Add-in Debug DLL Lock:** While SOLIDWORKS is open with the Debug add-in loaded, `ExecutionServer.AddIn/bin/x64/Debug/net48` is file-locked; close SOLIDWORKS before `dotnet build -c Debug` (or build `-c Release` / test `ExecutionServer.Tests.csproj`).
- **3D Part Scope Limits:** Side faces (`<node>.side_faces`), edges, cut faces, arcs, fillets, chamfers, patterns, and blind cuts measured from the far face are unsupported and refused by validation (K28).
- **Authoring Guide Sync:** Rule prose in `authoring_guide.py` (`_RULES`, `_UNSUPPORTED`) is hand-maintained; update it whenever validator rules change.
- **Frozen Drawing Caveats ([architecture review F1–F6](docs/superpowers/review/2026-11-05-architecture-review.md)):** Drawing checks D1/D2/D3/D7 currently pass on stubbed border/title-block read-back, and `check_drawing` can close an open drawing in a shared session — run only on scratch copies while frozen.
