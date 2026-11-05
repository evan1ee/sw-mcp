# Handoff

Last updated: 2026-11-05. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Current focus (owner decision, [ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md)):** drawing work is **frozen at `eea9389`** ([freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)). Development moves to the Part Feature Graph IR and an end-to-end MVP that produces a verified `.SLDPRT`. The owner approved the MVP [design](docs/superpowers/specs/2026-11-05-part-chain-mvp-design.md) and [plan](docs/superpowers/plans/2026-11-05-part-chain-mvp.md). Progress on `feat/part-chain-mvp` (nothing pushed): Task 0 done (live drawing baseline 5 passed, 1 skipped, recorded in the freeze record, `b12d938`); Task 1 done (live API [spike](docs/superpowers/review/2026-11-05-part-chain-spike.md), `840c520`); Task 2 committed (spec v1.30, `314523b`), its review was stopped before it finished, so Task 2 has not been reviewed (do that before Task 3). No part-chain code exists yet. Next: Task 3. Spike results that changed the design: no usable default template (new `part.template` setting), lookup by full path only, blind cut needs `Dir=true`, `FileCloseNotify` does not fire for API close (use `DestroyNotify2`). Two earlier spike runs ended with the owner's SOLIDWORKS exiting; the cause is unproven (the final run on a throwaway instance was clean). Never run live spikes against the owner's working session.
- **Frozen drawing state:** Annotation and dimension placement increment implemented and exercised by a live test script (Spec §11.4, §11.5, §11.10, §11.10.1, §6.5.2). This work was called "Phase 1c" here, but roadmap §18 defines Phase 1c as IR-built parts; by §18 it is partial Phase 1b, and Phase 1a acceptance is not yet met. The live test passes against local SOLIDWORKS 2025 SP0.1 with 0 violations, **but that is not evidence of drawing correctness for D1, D2, D3 or D7**: the add-in reads no line or text geometry and reports a fixed border and title block ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md) F1 to F3).
- **Architecture review:** completed 2026-11-05: [review](docs/superpowers/review/2026-11-05-architecture-review.md), [roadmap](docs/superpowers/review/2026-11-05-architecture-roadmap.md). The design and foundations are sound; the SOLIDWORKS adapters are prototype quality. Awaiting owner decisions (see Next Steps).
- **Spec:** v1.29 across all topic files in `docs/`. Section 18 now carries the current focus with the MVP's stages, and the paused Phase 1 work order (M0 to M11). Section 11.10 (Drawing Intent IR) and Section 11.10.1 (Resolved Scheme IR) normative schemas defined. Section 6.5.2 updated for 6 IPC annotation operations: `model_items.insert`, `dimensions.auto_arrange`, `center_mark.add`, `dimension.hide`, `dimension.show`, `dimension.move`. 5 open decisions remain: K3 (title block locators), J11 (draft-view switched indicator), K8 (snapshot keys), K9 (identity) and K10 (orchestrator form). Catalogue has 40 codes.
- **Branch:** `feat/part-chain-mvp`, from `feat/drawing-annotation-pipeline` at `961c629` (PR #12 merged to `main` at `eea9389`; the docs freeze commits are on that branch). Neither branch's newer commits are pushed.
- **Verification Suite Evidence:**
  - `uv run python scripts/generate_contracts.py --check` passes cleanly (0 drift across C# and Python contracts).
  - `uv run ruff check` passes. `uv run ruff format --check` passes (387 files, re-verified 2026-11-05 at `6dae76d`).
  - `uv run pyright` passes (0 errors, 0 warnings across all packages, apps, tests).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest -m "not live"` passes (2,712 passed, 6 deselected in 38.3s).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (241 passed, 0 failed in 1s).
  - `dotnet build apps/execution-server/ExecutionServer.sln` succeeded when last run with SOLIDWORKS closed. Not re-verified on 2026-11-05: the running SOLIDWORKS locks the add-in DLLs (MSB3027). `pyright`, `lint-imports`, `pytest` (2,712 passed) and `dotnet test` (241 passed) were re-verified that day; the live suite was not re-run.
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
- **Drawing Execution Pipeline Architecture Review & ADR-056:**
  - Authored comprehensive architectural review in `docs/superpowers/review/2026-11-05-drawing-execution-pipeline-review.md`.
  - Confirmed Evolutionary Architecture (no monolithic upfront plan IR; multi-stage orchestrator `ProduceDrawingRunner` across Spec §8.4 lifecycle).
  - Defined Tri-Tier Identity Contract: Deterministic Snapshot Keys (`s_/v_/a_` + SHA-256), Semantic IDs (`v_front`), Native CAD IDs.
  - Defined StagePlan (immutable intent), StageExecution (runtime status), ExecutionJournal (`journal.jsonl`), and ExecutionContext.
  - Defined Replay (audit vs replan vs live retry), Idempotency matrix, Rollback (compensating vs native undo vs checkpoint vs discard cleanup), and Custody rules.
  - Formatted CAD-neutral contracts (`annotations.import_model` with `vendor_extensions`) and pure Verification vs Reconciliation split with typed `CorrectionAction`s.
  - Formatted D1–D10 audit matrix preserving `NOT_EVALUATED`.
  - Authored `docs/adr/ADR-056-multi-stage-drawing-pipeline.md` and registered in `docs/adr/README.md`.
  - Committed in `db8a439`, with only the review's Python blocks reformatted. ADR-056 is Proposed; the review's "Approved for Implementation" label has no recorded owner approval. The edits it made to spec §6.5.3 and §8.4 were reverted at the owner's request (O2).
- **Whole-system architecture review (2026-11-05):**
  - Added `docs/superpowers/review/2026-11-05-architecture-review.md` (Revision 1: 40 findings, 31 contradictions, 15 proposals) and `2026-11-05-architecture-roadmap.md` (M0 to M11, dependencies reconciled in Revision 1). No production code, specification or ADR was changed. Revision 1 reviewed the same commit, with no live SOLIDWORKS run; `pytest` (2,712 passed) and `dotnet test` (241 passed) were re-verified.
  - **Critical findings:** no drawing geometry in read-back (F1); checks pass on unread data (F2); fabricated read-back values (F3); document custody not enforced, so `check_drawing` can close an engineer's open drawing (F4); operations ignore the addressed document (F5); operations can report success without working (F6).
  - **Major findings:** connection leak (F7); no production entry point (F8); no annotation identity (F9); Resolved Scheme defects (F10); no model read path (F11); Drawing Intent unused (F12); swallowed add-in errors (F13); hand-written IR models (F14); MCP conformance (F15); test blind spot at adapters (F16); status drift (F17); no live document identity contract (F39); snapshot keys are not identity, and the 11.5.1 duplicate-name rule has a gap (F40).
  - **Added in Revision 1:** snapshot completeness states (F2), operation success stages (F6), and the identity evaluation and test matrix (F9).
  - **Added in Revision 2:** full check of the pipeline review (review section 7.1): 20 contradictions with the spec, ADRs or itself, 5 unevidenced claims, 4 stale descriptions. That file was not edited. Its direction is sound, but it is not a verified baseline; do not implement from it until corrected.
  - **Spec cleanup after the review (O2 decided by the owner):** reverted the §6.5.3 and §8.4 edits and logged K8, K9 and K10 in `docs/specifications/open-decisions.md`.
- **Spec v1.28 (section 18 rewrite, at the owner's request):** `docs/specifications/roadmap.md` restructured for readability, with the review roadmap's M0 to M11 order added as the Phase 1 work order. Phase scope, acceptance criteria and A1 to A17 are unchanged. O1, O5 and O6 stay open, and the order remains a recommendation until O1 is decided.
- **Part chain MVP design and plan (v1.29):** written on `feat/part-chain-mvp`, with a builder check on the design, then revised after the [pre-implementation review](docs/superpowers/review/2026-11-05-part-chain-mvp-pre-implementation-review.md) (CONDITIONAL GO; F1 to F24 applied). No code changed, and SOLIDWORKS behaviour is unverified.

## Next Steps

**Part chain MVP (current work, ADR-057):**

1. **Owner:** approve the [MVP design](docs/superpowers/specs/2026-11-05-part-chain-mvp-design.md) and [plan](docs/superpowers/plans/2026-11-05-part-chain-mvp.md) as a whole. D1 to D5 were decided on 2026-11-05 (design section 14), including a temporary MVP exception to rule 13's Stop banner. The MVP runs from Claude over MCP to a verified `.SLDPRT`; first part: a 100 × 60 × 10 mm plate with four Ø8 mm through holes.
2. **After approval:** run plan Task 0 (live drawing baseline) and Task 1 (live API spike and A14). A failed assumption comes back to the owner before Task 2.
3. Follow the plan's revised order: spec v1.30, Part Feature Graph, IPC contracts, compiler and verification, add-in, store and journal, `plan` job, MCP tools, runtime, live acceptance, then the run from Claude and the owner's sign-off.

Do not continue drawing work, including the ADR-056 list below, until the owner lifts the freeze.

**Waiting for the freeze to lift. Decisions requiring owner approval** ([roadmap](docs/superpowers/review/2026-11-05-architecture-roadmap.md)):

- O1: Hold ADR-056's M1 to M6 until review milestones M1 to M3 are done. The two roadmaps conflict on sequence and reuse the same "M" numbers. **Not resolved here.**
- O3: Change the "Approved for Implementation" label on the pipeline review.
- O4: Adopt §18 phase names.
- O5: Pause `check_drawing` on real drawings in shared sessions until document safety is fixed.
- O6: Marked-only vs import-all for `model_items.insert`, decided from the A8 measurement.

**Recommended drawing order when the freeze lifts, pending those decisions:** correct the record and create the assumption register; make checks report `not_evaluated` for unread data; fix document safety and false success; implement real read-back with recorded fixtures and seeded-defect tests; then identity, runtime assembly, model read and `produce_drawing`.

**Already proposed by ADR-056 (not started; subject to O1):**

1. **Drawing Execution Pipeline Implementation (Roadmap M1–M6, ADR-056):**
   - **M1:** Identity Contract and Persistent Semantic References (C# deterministic SHA-256 snapshot keys; `sw_mcp_view_map` custom property view map; native semantic ID resolution in `FindView`).
   - **M2:** CAD-Neutral Operation Contracts (normalize `annotations.import_model`, add `vendor_extensions`, regenerate bindings).
   - **M3:** ExecutionContext, StagePlan, and ExecutionJournal (application data models and stage journal persistence).
   - **M4:** ProduceDrawingRunner and Lifecycle (Spec §8.4 state machine, cancellation boundaries, document custody).
   - **M5:** Verification and Reconciliation Loop (Spec §11.6 solver, typed `CorrectionAction`s, bounded 8-iteration retry loop).
   - **M6:** MCP Integration and Live Validation (`produce_drawing` MCP tool, live test against SOLIDWORKS 2025 SP0.1).
2. **Technical Spikes:**
   - **Spike S1:** View-level metadata via `IFeature` attributes (`IAttributeDef.CreateInstance5`) vs. document JSON custom property map.
   - **Spike S2:** Native undo recording reliability (`StartRecordingUndoObject`) across drawing view creation.
   - **Spike S3:** `AlignDimensions` API precision and boundary behavior across dense hole patterns.
3. **Phase 2a: Critical Dimension & Tolerance Verification Pipeline (Spec §11.6, §11.10.1):**
   - Connect `DrawingIntent` critical dimensions and GD&T callouts to `ResolvedScheme` for Checks D4 and D6.
4. **Open Decisions ([register](docs/specifications/open-decisions.md)):**
   - K3: Inspect standard ISO drawing formats (`standards/iso/templates/`) in SOLIDWORKS to define default zone locators for title-block field read-back.
   - J11: Detect whether a draft-quality view was switched to high quality in snapshot.
   - K8: Snapshot keys when native names change or repeat.
   - K9: How view and annotation identity persists across sessions.
   - K10: The form of the `produce_drawing` orchestrator (settled through O1 and ADR-056).

## Known Issues

- **Use `check_drawing` on scratch copies only:** the frozen code can close an engineer's open drawing (F4, F5). The fix is not scheduled while drawings are frozen, unless the part chain needs the shared part of it.
- **K3 remains open:** Reading title-block fields back from owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot does not yet report whether a draft-quality view was switched to high quality; awaiting interactive inspection.
- **Do not treat a D1, D2, D3 or D7 `pass` as evidence yet** (F1 to F3). No report can reach `done` today only because D4, D6 and D9 are always `not_evaluated`; implementing them first would remove that protection.
- **Unverified SOLIDWORKS behaviour:** whether `CloseDoc` discards unsaved changes (F4); whether hidden annotations are enumerated (X3); which `SynchronizationContext` path runs (F21); whether the second job in one core connects (F7). Assumptions A1 to A17 have no recorded outcomes, because `docs/specifications/assumptions.md` does not exist.
