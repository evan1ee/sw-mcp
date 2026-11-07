# Handoff

Last updated: 2026-11-07. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Post-MVP 3D Part Tech-Debt Cleanup (2026-11-07, spec v1.38, branch `chore/clear-part-mvp-tech-debt`):**
  - **Debt 1 (K29 Datum-Plane Generalization — Closed):** Generalized cap-face coordinate frames (`<extrude>.start_face` and `<extrude>.end_face`) across all three standard datum planes (`plane:front`, `plane:top`, `plane:right`) in [`packages/cad-ir`](packages/cad-ir/src/cad_ir/part_feature_graph/faces.py), [`packages/cad-geometry`](packages/cad-geometry/src/cad_geometry/cap_faces.py), [`packages/cad-references`](packages/cad-references/src/cad_references/cap_face_signatures.py), [`packages/cad-compiler`](packages/cad-compiler/src/cad_compiler/part.py), [`packages/cad-verification`](packages/cad-verification/src/cad_verification/part.py), [`packages/cad-application`](packages/cad-application/src/cad_application/authoring_guide.py), [`FaceSpike.cs`](apps/execution-server/ExecutionServer.AddIn/Parts/FaceSpike.cs), and [`ExecutionServer.Tests`](apps/execution-server/ExecutionServer.Tests/Parts/FaceSignatureTests.cs). Live SOLIDWORKS 2025 verification proved that on `plane:front` and `plane:right`, `start_face` mirrors the sketch `x` axis (`x_sign = -1, y_sign = 1`), whereas on `plane:top` (`normal = (0, -1, 0)`), SOLIDWORKS keeps `x = (1, 0, 0)` and mirrors the sketch `y` axis (`y = (0, 0, 1)`, `x_sign = 1, y_sign = -1`). Recorded in [§5.7.4](docs/architecture/feature-schema-guide.md#574-sketches) and [ADR-070](docs/adr/ADR-070-sketch-on-extrude-cap-face.md); K29 moved to Closed in [open-decisions.md](docs/specifications/open-decisions.md).
  - **Debt 2 (3D Part Live Test Coverage):** Added `test_blind_hole_in_start_face`, `test_blind_hole_across_datum_and_cap_faces` (`plane:front`, `plane:top`, `plane:right` × `end_face`, `start_face` with off-center holes at `(10.0, 5.0)`), and `test_block_centre_hole` in [`tests/live/test_live_part_chain.py`](tests/live/test_live_part_chain.py) with `.SLDPRT` cleanup in `finally:` blocks. **Verified live in SOLIDWORKS 2025:** `uv run pytest tests/live/test_live_part_chain.py -m live -v` passed **19 passed, 1 skipped in 105.69s** (`test_template_with_reordered_planes` skips because SOLIDWORKS refuses to reorder/delete standard planes).
  - **Debt 3 (Prompt-to-Part-IR Evaluation Baseline):** Added `blind_hole_start_face` to [`authoring_eval`](packages/cad-application/src/cad_application/authoring_eval/cases.py) (13 cases total: 8 build, 5 refuse), recorded the evaluated baseline in [`tests/cad-benchmark/part_ir_baseline_answers.json`](tests/cad-benchmark/part_ir_baseline_answers.json) (**13/13 passed, 100%** via `uv run python scripts/score_part_ir.py tests/cad-benchmark/part_ir_baseline_answers.json`), and added automated benchmark tests in [`tests/cad-benchmark/test_part_ir_benchmark.py`](tests/cad-benchmark/test_part_ir_benchmark.py).
  - **Debt 4 (3D Part COM Interop Cleanup & Contract Hygiene):** Hardened `ComScope` tracking of `IFeature`, `IFace2`, `ISurface`, `ISketchSegment`, and `IMassProperty` COM proxies across `FeatureLookup.cs`, `CapFaceSketch.cs`, `SketchAdapter.cs`, `FeatureAdapter.cs`, and `PartMeasureAdapter.cs`; added untitled document cleanup on `SaveAs4` failure in `PartCreationAdapter.cs`; translated `COMException` on feature creation/rebuild to `IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, ...)` in `FeatureAdapter.cs`; and hardened `PartObservation.from_mapping` in [`contracts.py`](packages/cad-verification/src/cad_verification/api/contracts.py) to reject boolean/non-integer `error_code`/`entity_count`/`solid_body_count` and non-boolean `is_warning`/`suppressed` as `not_evaluated` (`malformed_data`).

- **Part MCP MVP review (2026-11-06):** [review](docs/superpowers/review/2026-11-06-part-mcp-mvp-review.md) found the MVP complete and aligned with the design, ADR-057 and the layering rules, so no code was changed. Follow-ups done the same day: `CorePipeClient` now reconnects on the next call after a dropped connection, rediscovering the core through the session file (a request that failed mid-flight is not resent), tested in `apps/mcp-server/tests/test_client_reconnect.py`; `.mcp.json` launches `.venv\Scripts\python.exe -m mcp_server`, so a running front-end no longer locks `uv sync`/`uv run`. A real plate job is recorded in `tests/fixtures/ipc/plan_plate_live_recorded.jsonl` by `scripts/record_plate_transcript.py` and replays in the contract tests; `plan_plate_recorded.jsonl` is still synthetic.

- **Sketch on a cap face (2026-11-06, spec v1.37, PR 14; generalized in v1.38):** `sketch.plane` may be `<extrude>.end_face` or `.start_face` ([ADR-070](docs/adr/ADR-070-sketch-on-extrude-cap-face.md), [face spike](docs/superpowers/review/2026-11-06-face-sketch-spike.md), [plan](docs/superpowers/plans/2026-11-06-face-reference-sketches.md)). Verified across all 6 datum-and-cap combinations in unit and live SOLIDWORKS 2025 tests.

- **Agent IR authoring (2026-11-06, PR 14, spec v1.36; baseline recorded in v1.38):** an MCP client can turn a user's request into a valid graph with `get_authoring_guide`, the server `instructions`, better validator messages and a 13-prompt evaluation set (`13/13 passed` baseline in `tests/cad-benchmark/part_ir_baseline_answers.json`). Unsupported requests are refused, never approximated (owner decision). Plan: [agent IR authoring](docs/superpowers/plans/2026-11-06-agent-ir-authoring.md). `.mcp.json` registers the `sw-mcp` server, and `get_authoring_guide` is listed by a fresh session.

- **Current focus (owner decision, [ADR-057](docs/adr/ADR-057-freeze-drawings-build-part-chain-first.md)):** drawing work is **frozen at `eea9389`** ([freeze record](docs/superpowers/review/2026-11-05-drawing-freeze.md)). Development moves to the Part Feature Graph IR and an end-to-end MVP that produces a verified `.SLDPRT`. The owner approved the MVP [design](docs/superpowers/specs/2026-11-05-part-chain-mvp-design.md) and [plan](docs/superpowers/plans/2026-11-05-part-chain-mvp.md). **The part chain MVP is done and signed off by the owner on 2026-11-06** (details in [section 18](docs/specifications/roadmap.md#current-focus-the-part-chain-adr-057)). Tasks 0 to 13 are complete on `feat/part-chain-mvp`. The sign-off run found and fixed three defects (`cd70b87`, `32f4905`).
- **Frozen drawing state:** Annotation and dimension placement increment implemented and exercised by a live test script (Spec §11.4, §11.5, §11.10, §11.10.1, §6.5.2). This work was called "Phase 1c" here, but roadmap §18 defines Phase 1c as IR-built parts; by §18 it is partial Phase 1b, and Phase 1a acceptance is not yet met. The live test passes against local SOLIDWORKS 2025 SP0.1 with 0 violations, **but that is not evidence of drawing correctness for D1, D2, D3 or D7**: the add-in reads no line or text geometry and reports a fixed border and title block ([architecture review](docs/superpowers/review/2026-11-05-architecture-review.md) F1 to F3).
- **Architecture review:** completed 2026-11-05: [review](docs/superpowers/review/2026-11-05-architecture-review.md), [roadmap](docs/superpowers/review/2026-11-05-architecture-roadmap.md). The design and foundations are sound; the SOLIDWORKS adapters are prototype quality.
- **SOLIDWORKS adapter design (Accepted by the owner, 2026-11-05; committed as `360005f`):** [8.8 architecture](docs/architecture/solidworks-adapter.md), [8.9 interface specification](docs/specifications/solidworks-adapter.md), ADR-058 to ADR-063, [roadmap](docs/plans/solidworks-adapter-roadmap.md).
- **Verifiable compilation gap analysis (2026-11-05, at `0222b15`):** [review](docs/superpowers/review/2026-11-05-verifiable-compilation-gap-analysis.md). The owner accepted [ADR-064](docs/adr/ADR-064-per-operation-verification-contracts.md) on 2026-11-05 and decided K22 (a feature warning blocks a commit in the MVP). V14 settled in `026229f`: the plan hash includes the pinned revision (6.7.4). Wrong verdicts V5, V6 and V7 are fixed in `98a3c31`.
- **Roadmap A0 is done (spec v1.34):** schemas for evidence, contracts, `observation`, `document.rebuild`, `op_verified` and two new error codes.
- **Architecture reference (spec v1.35, 2026-11-05; documents only, awaiting the owner):** [§22 IR](docs/specifications/ir-specification.md) and [§23 Compiler](docs/specifications/compiler-architecture-specification.md) are new and Proposed. The adapter was extended in place, in [8.9.11 to 8.9.14](docs/specifications/solidworks-adapter.md). The rest of `docs/architecture/` was aligned, with wording fixes listed in the [changelog](docs/specifications/CHANGELOG.md). ADR-065 to ADR-069 are Proposed and not applied. K23 to K28 are new in the [register](docs/specifications/open-decisions.md), which now has 21 open items. API facts came from reflecting the installed 2025 interop and reading its installed help; nothing was run, so those rows are marked ◐.
- **Spec:** v1.38 across all topic files in `docs/`. Section 18 now carries the current focus with the MVP's stages, and the paused Phase 1 work order (M0 to M11).
- **Branch:** `chore/clear-part-mvp-tech-debt`.
- **Verification Suite Evidence (2026-11-07):**
  - `uv run python scripts/generate_contracts.py && git diff --exit-code packages/cad-protocol apps/execution-server` passes cleanly (0 drift across C# and Python contracts).
  - `uv run ruff check .` passes. `uv run ruff format --check` passes (481 files).
  - `uv run pyright` passes (0 errors, 0 warnings across all packages, apps, tests).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest --ignore=tests/drawing-benchmark` passes (**3,411 passed, 38 deselected in 62.94s**).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (**346 passed, 0 failed, 0 skipped in 2s**).
  - `dotnet build apps/execution-server/ExecutionServer.sln -c Release` passes cleanly (0 warnings, 0 errors in 2.75s).
  - `uv run python scripts/score_part_ir.py --prompts` and `uv run python scripts/score_part_ir.py tests/cad-benchmark/part_ir_baseline_answers.json` pass (**13/13 passed, 100%**).
  - `uv run pytest tests/live/test_live_part_chain.py -m live -v` passes (**19 passed, 1 skipped in 105.69s** against SOLIDWORKS 2025).

## Changes Made

- **Post-MVP 3D Part Tech-Debt Cleanup (2026-11-07):**
  - **K29 Datum-Plane Generalization (`9a8ff3e` + live frame fix):** Updated `FaceFrame.to_model`, `face_frame`, and `in_base_frame` in `packages/cad-ir/src/cad_ir/part_feature_graph/faces.py`; implemented `cap_face_frame` and `project_cap_face_point` in `packages/cad-geometry/src/cad_geometry/cap_faces.py`; implemented `resolve_cap_face_signature` in `packages/cad-references/src/cad_references/cap_face_signatures.py`; wired `_face_params` in `packages/cad-compiler/src/cad_compiler/part.py` to `resolve_cap_face_signature`; updated `expected_geometry` in `packages/cad-verification/src/cad_verification/part.py` to project cap-face cuts and cylinders via `FaceFrame.to_model`; updated `authoring_guide.py` and `FaceSpike.cs`; added parameterized tests covering all 6 datum-and-cap combinations (`plane:front`, `plane:top`, `plane:right` × `start_face`, `end_face`) in Python and C#.
  - **COM Interop Cleanup & Contract Hygiene (`8d8e1b1`):** Updated `FeatureLookup.cs`, `CapFaceSketch.cs`, `SketchAdapter.cs`, `FeatureAdapter.cs`, `PartCreationAdapter.cs`, and `PartMeasureAdapter.cs` for `ComScope` lifetime safety, untitled document cleanup on `SaveAs4` failure, and `COMException` translation to `BACKEND_REBUILD_ERROR`; hardened `packages/cad-verification/src/cad_verification/api/contracts.py` against boolean/integer and non-boolean type coercion.
  - **Prompt-to-Part-IR Evaluation Baseline (`ccb337c`):** Added `blind_hole_start_face` to `cases.py` and `references.py`, added `--baseline` flag to `scripts/score_part_ir.py`, generated `tests/cad-benchmark/part_ir_baseline_answers.json`, and added `tests/cad-benchmark/test_part_ir_benchmark.py`.
  - **Live 3D Part Tests & Spec v1.38 (`7c550c2`, `870bf44`):** Added `test_blind_hole_in_start_face`, `test_blind_hole_across_datum_and_cap_faces` (with off-center holes at `(10.0, 5.0)`), and `test_block_centre_hole` to `tests/live/test_live_part_chain.py`; updated §5.7.4, ADR-070, `open-decisions.md` (closing K29), and bumped specification to v1.38.

- **Sketch on a cap face:** `cad_ir/part_feature_graph/faces.py` (frames, `in_base_frame`); validator `_check_face_planes`; lowering emits `face` on `sketch.create` and `host` on a cut's `feature.create` (stage `feature_lowering` 0.3.0, golden plan provenance updated); `expected_geometry` places a face cut; `resolve_node_refs` in `plan_job.py`; C# `FaceSignature.cs` (CAD-free, 8 tests), `CapFaceSketch.cs`, `FeatureLookup.cs`, and the blind direction by host in `FeatureAdapter`. The spike program has a `face` mode (`tests/live/spikes/PartChainSpike/FaceSpike.cs`). Guide and evaluation set updated (12 prompts: 9 build, 3 refuse).

- **Agent IR authoring:** `cad_application/authoring_guide.py` and the `get_authoring_guide` tool (`schemas/mcp/get_authoring_guide.json`); `INSTRUCTIONS` in `mcp_server/server/app.py`; fix hints in five `semantic.py` messages; `cad_application/authoring_eval/` (11 prompts: 8 build, 3 refuse; checker; references) scored by `scripts/score_part_ir.py`. It is a tool and not an MCP resource because the front-end may import no `cad_*` package. Review fixes on the branch: separate sketch loops are rejected (`_is_connected` in `semantic.py`), `AnnotationPlacementAdapter` no longer releases `IModelDoc2` (G1), `SketchAdapter.CreateSketch` closes a half-built sketch on failure.

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

- **Store, Journal and Recovery Rules (Task 9a, committed as `b995c2a`):**
  - Updated `schemas/store/v0.json` with `PublishIntentRecord`, `PublishedRecord`, `PartRecord`, `DocumentRecord.action` containing `create`, and `JobRecord.part_result`. Regenerated schemas (`cad_ir.generated.schemas`).
  - Added schema test fixtures under `tests/fixtures/schemas/store/{valid,invalid}/`.
  - Implemented `DocumentAction` with `"create"`, `_action()` strict validation, `OpVerifiedRecord`, `PublishIntentRecord`, `PublishedRecord` in `journal_records.py`.
  - Added `part_result` to `JobRecord` (`job_records.py`), ensuring v0 backwards compatibility.
  - Implemented `PartRecord` in `cad_application/store/records.py`.
  - Added `FileSystem.rename_new` to `ports.py`, `MemoryFileSystem`, and `OsFileSystem` (`MoveFileExW` on Windows with `MOVEFILE_WRITE_THROUGH = 0x8` and write-through, no replacement).
  - Extended `paths.authorize` for `expect="new_file"` checking suffix, parent directory existence, target non-existence (`AUTH_SOURCE_WRITE_NOT_ALLOWED`), and PDM vault rejection (`AUTH_SOURCE_WRITE_NOT_ALLOWED`).
  - Added `put_plan` (returns `False` on reuse), `put_part_revision` (spec 3.4.5 revision 1, canonical byte reuse, `REV_CONFLICT`), `get_part_revision`, and `put_part_record` to `FileStore`.
  - Updated `journal.recover` to mark created documents unknown after crashes and compare target fingerprints on unconfirmed publish intent (`JobWarning("published_unconfirmed", ...)`).
  - Added comprehensive test suites: `test_part_store.py`, `test_rename_new.py`, `test_new_file_authorize` in `test_paths.py`, and `test_part_recovery.py`.
  - Reviewed and verified clean (APPROVED). Committed as `b995c2a`.

## Next Steps

- **Merge `chore/clear-part-mvp-tech-debt` into `main`:** All four post-MVP 3D part tech-debt items (K29 datum-plane generalization, live test coverage for `start_face`/non-front planes/`block_centre_hole`, `score_part_ir.py` evaluation baseline, and COM/contract hygiene) are resolved and verified against SOLIDWORKS 2025.
- **Later, separate spec and ADR:** side faces (`<node>.side_faces`, K23, K26, K28), edges, arcs, fillets, chamfers, and linear/circular patterns. The authoring guide lists them as unsupported until then.

**Part chain MVP (current work, ADR-057):** the MVP runs from Claude over MCP to a verified `.SLDPRT`; first part: a 100 × 60 × 10 mm plate with four Ø8 mm through holes.

Current order:
- Tasks 0 to 13: complete. Next: the owner decides what follows (merge the branch, lift the freeze, more feature types).
- The MVP covers only `sketch`, `extrude` and `cut_extrude`; other features are refused by validation.

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

- **Rebuild with SOLIDWORKS closed:** the add-in DLLs (`bin/x64/Debug/net48`) are locked while SOLIDWORKS runs with the Debug add-in loaded, so `dotnet build -c Debug` on `ExecutionServer.AddIn` requires closing SOLIDWORKS first (while `dotnet build -c Release` and `dotnet test` succeed while SOLIDWORKS is open).
- **Non-cap faces (`side_faces`), edges, and faces of cuts stay unsupported (K28):** only `<extrude>.start_face` and `<extrude>.end_face` on `plane:front`, `plane:top`, and `plane:right` are supported.

- **Authoring guide limits are hand-written** (`_RULES`, `_UNSUPPORTED` in `authoring_guide.py`); tests check that the examples validate and that planes and node types match the code, not that every rule sentence matches the validator.
- **Blind cut direction from the far face is not expressible:** a blind cut starts at its sketch plane. The guide tells the agent to refuse a hole "in the top face" with a depth.

- **Part chain, found in the sign-off run (fixed):** tool schemas carried unresolved `$ref`s (clients sent `graph` as a string); plan files were named `sha256:<hex>`, and the colon fails on Windows from the second job in a store; the `features` check counted the template's default tree. Not covered by earlier tests: the in-memory filesystem accepts colons, and live tests used a fresh store per job.
- **Part chain, open:** the recorded transcript `plan_plate_recorded.jsonl` is synthetic (`C:\Work` paths), not a recording of real SOLIDWORKS. The owner opened only the first plate in SOLIDWORKS. `known-stores.json` and `D:\CAD\scratch` hold test leftovers.
- **Use `check_drawing` on scratch copies only:** the frozen code can close an engineer's open drawing (F4, F5). The fix is not scheduled while drawings are frozen, unless the part chain needs the shared part of it.
- **K3 remains open:** Reading title-block fields back from owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot does not yet report whether a draft-quality view was switched to high quality; awaiting interactive inspection.
- **Do not treat a D1, D2, D3 or D7 `pass` as evidence yet** (F1 to F3). No report can reach `done` today only because D4, D6 and D9 are always `not_evaluated`; implementing them first would remove that protection.
- **Unverified SOLIDWORKS behaviour:** whether `CloseDoc` discards unsaved changes (F4); whether hidden annotations are enumerated (X3); which `SynchronizationContext` path runs (F21); whether the second job in one core connects (F7). Assumptions A1 to A17 have no recorded outcomes, because `docs/specifications/assumptions.md` does not exist.
