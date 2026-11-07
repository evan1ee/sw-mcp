# Handoff

Last updated: 2026-11-07 (branch `docs/implementation-checklists`, spec v1.39).
> **Handoff Rule ([AGENTS.md §5](AGENTS.md#5-session-handoff)):** Keep this file as short as possible. Rewrite in place — **never** append an incremental history (`git log` and [`CHANGELOG.md`](docs/specifications/CHANGELOG.md) record history). Keep only the current state snapshot, the latest session's **Changes Made**, prioritized **Next Steps**, and active **Known Issues**, linking to `docs/` instead of repeating details.

## Current State

- **Active Focus — 3D Part Chain ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [Roadmap §18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)):**
  - **Part Chain MVP + Post-MVP Tech-Debt Cleanup Complete on `main`:** End-to-end MCP-to-`.SLDPRT` pipeline supports `sketch` (lines and circles; a rectangle is an authoring recipe of four lines), boss `extrude`, and `cut_extrude` (`blind` / `through_all_both`) on standard datum planes (`plane:front`, `plane:top`, `plane:right`) and extrude cap faces (`<extrude>.start_face`, `<extrude>.end_face` per [ADR-070](docs/adr/ADR-070-sketch-on-extrude-cap-face.md) & [§5.7.4](docs/architecture/feature-schema-guide.md#574-sketches)).
  - **Agent IR Authoring:** `get_authoring_guide` MCP tool + 13-case benchmark in [`tests/cad-benchmark/`](tests/cad-benchmark/test_part_ir_benchmark.py) (`13/13` passing: 8 positive builds, 5 refusals).
  - **Architecture Reference (spec v1.35+, awaiting owner sign-off):** Proposed [§22 IR](docs/specifications/ir-specification.md), [§23 Compiler](docs/specifications/compiler-architecture-specification.md), and ADR-065..069; open decisions tracked in [`open-decisions.md`](docs/specifications/open-decisions.md).
- **2D Drawings — Frozen at `eea9389` ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)):**
  - Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark` until the owner lifts the freeze.
- **Verification Baseline (2026-11-07 on `main`):**
  - Contracts (`generate_contracts.py`), `ruff`, `pyright`, `lint-imports`: **0 errors/drift**.
  - Python tests (`pytest --ignore=tests/drawing-benchmark`): **3,451 passed** (on this branch).
  - C# tests (`dotnet test apps/execution-server`): **346 passed**; `dotnet build -c Release`: **0 warnings/errors**.
  - Prompt-to-IR benchmark (`scripts/score_part_ir.py`): **13/13 passed**.
  - Live SOLIDWORKS 2025 (`pytest tests/live/test_live_part_chain.py -m live`): **19 passed, 1 skipped** (`105.7s`); every run belongs in the [live run record](docs/implementation/README.md#live-run-record).

## Changes Made

- **Implementation Checklists (branch `docs/implementation-checklists`, docs and tooling only):**
  - Added [`docs/implementation/`](docs/implementation/README.md): the single source of truth for Sketch and Part Feature status (stable IDs, one row per option, six-layer tracking), plus the audit script [`scripts/check_implementation_checklists.py`](scripts/check_implementation_checklists.py), which reads its conventions from the index and derives all counts. CI runs the audit.
  - Spec v1.39: [§22.12](docs/specifications/ir-specification.md#2212-implementation-status) now points to the tracker, and K30 and K31 log the gaps found by the audit. No contract, schema or source changes. Owner decisions and the live evidence still needed are listed in the index.

## Next Steps

1. **Owner Decision on Next 3D Part Milestone (pick rows from the [checklists](docs/implementation/README.md) and its owner-decision list) ([Roadmap §18](docs/specifications/roadmap.md)):**
   - Expand 3D Part IR feature coverage (arcs, fillets, chamfers, linear/circular patterns, or side-face references `<node>.side_faces` under K23/K26/K28) via new spec + ADR before implementation.
2. **When Drawing Freeze Lifts ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md), [roadmap](docs/superpowers/review/2026-11-05-architecture-roadmap.md)):**
   - Resolve owner decisions O1–O6 and open items K3, K8–K10, J11 in [`open-decisions.md`](docs/specifications/open-decisions.md), then execute milestones M0–M11 (document custody, real geometry read-back, `not_evaluated` guards, and `produce_drawing`).

## Known Issues

- **Add-in Debug DLL Lock:** While SOLIDWORKS is open with the Debug add-in loaded, `ExecutionServer.AddIn/bin/x64/Debug/net48` is file-locked; close SOLIDWORKS before `dotnet build -c Debug` (or build `-c Release` / test `ExecutionServer.Tests.csproj`).
- **3D Part Scope Limits:** Side faces (`<node>.side_faces`), edges, cut faces, arcs, fillets, chamfers, patterns, and blind cuts measured from the far face are unsupported and refused by validation (K28).
- **Authoring Guide Sync:** Rule prose in `authoring_guide.py` (`_RULES`, `_UNSUPPORTED`) is hand-maintained; update it whenever validator rules change.
- **Frozen Drawing Caveats ([architecture review F1–F6](docs/superpowers/review/2026-11-05-architecture-review.md)):** Drawing checks D1/D2/D3/D7 currently pass on stubbed border/title-block read-back, and `check_drawing` can close an open drawing in a shared session — run only on scratch copies while frozen.
