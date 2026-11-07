# Handoff

Last updated: 2026-11-07 (branch `feat/revolve-features`, spec v1.46).
> **Handoff Rule ([AGENTS.md §5](AGENTS.md#5-session-handoff)):** Keep this file as short as possible. Rewrite in place — **never** append an incremental history (`git log` and [`CHANGELOG.md`](docs/specifications/CHANGELOG.md) record history). Keep only the current state snapshot, the latest session's **Changes Made**, prioritized **Next Steps**, and active **Known Issues**, linking to `docs/` instead of repeating details.

## Current State

- **Active Focus — 3D Part Chain ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [Roadmap §18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)):**
  - **Revolved Features & Centerline Construction Geometry (`BF-REV-001`..`016`, `CF-REV-001`..`006`, `SK-ENT-002`, `SK-ENT-003`) Complete:** Revolved boss and cut features implemented end-to-end (Spec v1.46, [ADR-077](docs/adr/ADR-077-revolve-features.md)) with pure core IR lowering, Pappus's centroid theorem and circumferential groove split-cylinder verification geometry, C# add-in adapters with Mark 0 profile and Mark 4 revolution axis selection via centerline segments, sketch centerline creation (`Line.construction`), authoring guide rules, and benchmark fixtures (`turned_shaft`, `grooved_shaft`). Verified live against SOLIDWORKS 2025 (`test_live_revolve_shaft`, `test_live_revolve_groove`, `test_live_direct_revolve_ops`) and promoted to `Verified`.
  - **Agent IR Authoring:** `get_authoring_guide` MCP tool + 20-case benchmark in [`tests/cad-benchmark/`](tests/cad-benchmark/test_part_ir_benchmark.py) (`20/20` passing with `turned_shaft` and `grooved_shaft`, 17 positive builds, 3 refusals).
- **2D Drawings — Frozen at `eea9389` ([ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md), [freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)):**
  - Do not modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas, or `tests/drawing-benchmark` until the owner lifts the freeze.
- **Verification Baseline (2026-11-07 on `feat/revolve-features`):**
  - Contracts (`generate_contracts.py --check`), `ruff check`, `ruff format --check`, `pyright`, `lint-imports`: **0 errors/drift**.
  - Implementation checklists audit (`check_implementation_checklists.py`): **587 items, 71 capabilities, 0 problems** (76 verified items; `base-features.md`, `cut-features.md`, and `sketch-entities.md` updated).
  - Python tests (`pytest --ignore=tests/drawing-benchmark`): **3,556 passed, 51 deselected**.
  - Live SOLIDWORKS 2025 tests (`pytest tests/live -m live`): **32 passed, 1 skipped cleanly** (including `test_live_revolve_shaft`, `test_live_revolve_groove`, `test_live_direct_revolve_ops`).
  - C# tests (`dotnet test apps/execution-server`): **359 passed**; `dotnet build -c Release` & `-c Debug`: **0 warnings/errors**.
  - Prompt-to-IR benchmark (`scripts/score_part_ir.py`): **20/20 passed**.

## Changes Made

- **Revolved Features & Centerline Construction Geometry (`BF-REV-001`..`016`, `CF-REV-001`..`006`, `SK-ENT-002`, `SK-ENT-003`, [ADR-077](docs/adr/ADR-077-revolve-features.md), Spec v1.46):**
  - **Spec & Schemas:** Added [ADR-077](docs/adr/ADR-077-revolve-features.md); added `schemas/part-feature-graph/features/revolve.json` and `cut_revolve.json`; updated `schemas/part-feature-graph/primitives/line.json` with `construction: boolean`; updated `part-feature-graph/v0.json` with `Revolve` and `CutRevolve`; updated `ipc/ops/feature.create.json` with `revolve` and `cut_revolve` types and fields (`axis`, `angle_deg`, `thin_wall`); regenerated Python and C# contracts; bumped spec to v1.46 across 35 topic files, README, and CHANGELOG.
  - **Pure Core IR & Compiler:** Added `Revolve`, `CutRevolve`, and `Line.construction` in `cad-ir`; added semantic validation (axis reference, angle range, profile sketch, planar sketch, construction lines) in `cad-compiler`; implemented lowering to `feature.create` operation in `lower.py`; registered in `registry.py` and `profile.py`.
  - **Verification Engine:** Implemented closed-form revolve expected geometry in `cad-verification/part.py` using Pappus's Centroid Theorem ($V = 2\pi R_c A$), circumferential groove surface area delta ($\Delta A = 2\pi R_{\text{floor}} h - 2\pi R_{\text{max}} h + 2\pi(R_{\text{max}}^2 - R_{\text{floor}}^2)$), and outer cylinder splitting logic; updated contract tests for `native_type="Revolution"` and `"RevCut"`.
  - **Execution Server:** Implemented centerline creation in `SketchAdapter.cs` via `sm.CreateCenterLine` when `entity.Construction == true`; implemented `Revolve` and `CutRevolve` in `FeatureAdapter.cs` calling `FeatureRevolve2` with Mark 0 (profile sketch) and Mark 4 (axis sketch segment via `SelectRevolveAxis`), with ComScope tracking and observation type mapping; unit tests in `RevolveParamTests.cs`.
  - **Authoring & Benchmark:** Updated `authoring_guide.py` and `list_feature_types.py` (MVP feature types count to 8) with revolve rules and `turned_shaft` worked example; added `turned_shaft` and `grooved_shaft` to `cases.py`, `references.py`, and `part_ir_baseline_answers.json` (`20/20` scored passing).
  - **Live SOLIDWORKS Verification & Promotion:** Added `test_live_revolve_shaft`, `test_live_revolve_groove`, and `test_live_direct_revolve_ops` in `tests/live/test_live_part_chain.py`; resolved sketch axis references (`<sketch>.cl`) in `plan_job.py`; verified against live SOLIDWORKS 2025; promoted revolve and centerline checklist items to `Verified`.

## Next Steps

1. **Commit, Push, PR & Merge `feat/revolve-features`:**
   - Commit changes, push to origin and github, open PR, and merge into `main`.
2. **Next 3D Part Milestone (pick from [checklists](docs/implementation/README.md)):**
   - **Reference Planes / Reference Geometry (`REF-PLN-001`..`REF-PLN-007`):** Implement offset, angle, and mid-plane reference planes to support features on angled faces, offset sketches, and mirrors.
   - **Hole Wizard / Standard Holes (`CF-HLW-001`..`CF-HLW-012`):** Implement counterbore, countersink, and tapped standard hole features.
   - **Semantic Edge References & Fillets/Chamfers (`BF-FIL`, `BF-CHM`, K23/K28):** Draft ADR and grammar for persistent semantic edge references required by constant-radius fillets and chamfers.
3. **When Drawing Freeze Lifts ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md)):**
   - Resolve owner decisions O1–O6 and open items K3, K8–K10, J11 in [`open-decisions.md`](docs/specifications/open-decisions.md).

## Known Issues

- **Add-in DLL Lock:** While SOLIDWORKS is running with the add-in loaded, `sw-mcp.AddIn.dll` is file-locked; close SOLIDWORKS before rebuilding or re-registering.
- **3D Part Scope Limits:** Side faces (`<node>.side_faces`), edges, cut faces, fillets, chamfers, and blind cuts measured from the far face are unsupported and refused by validation (K28).
- **Frozen Drawing Caveats ([architecture review F1–F6](docs/superpowers/review/2026-11-05-architecture-review.md)):** Drawing checks D1/D2/D3/D7 currently pass on stubbed border/title-block read-back; run only on scratch copies while frozen.
