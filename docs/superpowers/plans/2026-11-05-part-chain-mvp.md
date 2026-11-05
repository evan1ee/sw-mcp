# Part Chain MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude asks for a part over MCP; the core validates and compiles a Part Feature Graph, the add-in builds it in SOLIDWORKS, and a `.SLDPRT` appears at the target path only if measurements match the IR.

**Architecture:** New pure code in `cad_ir.part_feature_graph`, `cad-compiler` and `cad-verification`. A new `plan` job in `cad-application` on the existing engine and journal. New add-in adapters under `Adapters/Parts/`, ownership and dispatch in `ExecutionServer.Core`, and real entry points with the official MCP SDK on the front-end.

**Tech Stack:** Python 3.13, uv, pytest, pyright strict, official `mcp` SDK; C# .NET Framework 4.8, SOLIDWORKS 2025 COM interop, tests in `ExecutionServer.Tests`.

**Spec:** [`docs/superpowers/specs/2026-11-05-part-chain-mvp-design.md`](../specs/2026-11-05-part-chain-mvp-design.md). Read it first. "Design 7" means its section 7. Findings (`F1`) are from the [pre-implementation review](../review/2026-11-05-part-chain-mvp-pre-implementation-review.md).

**Gates.** Tasks 0 and 1 can start once the owner approves this plan, since they change no product code. The owner decided D1 to D5 on 2026-11-05 (design 14). The spike's answers must be recorded before Task 3. Crash-point tests in Task 9a must pass before Task 12.

**Order.** Task numbers match the review, so they don't run in numeric order. Run them in the order written here, except that Task 7c, written after 7b, runs before it. Tasks 4 and 5 can run alongside Tasks 7a to 8.

```text
T0 Baseline ─► T1 Spike and A14 ─► T2 Spec v1.30 ─► T3 IR ─► T6 IPC contracts
                                                               │
                             ┌─────────────────────────────────┤
                             ▼                                 ▼
                    T4 Compiler + T5 Verification       T7a Dispatch, ownership
                             │                                 ▼
                             │                          T7c Dispatcher, capabilities
                             │                                 ▼
                             │                          T7b Events, instance IDs
                             │                                 ▼
                             │                          T8 Part adapters
                             ▼                                 │
                    T9a Store, journal, recovery               │
                             ▼                                 │
                    T9b Plan job ◄─────────────────────────────┘
                             ▼
                    T10 Tools ─► T11 Runtime ─► T12 Live ─► T13 Run from Claude
```

## Global Constraints

- **Branch:** `feat/part-chain-mvp`. Commit with explicit paths only. Never push without the owner's request.
- **Drawing freeze (ADR-057):** do not edit `packages/cad-drawing/`, `cad_application/drawing/`, `jobs/check_drawing.py`, or `Adapters/Drawings/`. If a change forces an edit to one of these, stop and bring it to the owner.
- **Purity (G2):** `cad-ir`, `cad-compiler` and `cad-verification` have no I/O, clock or CAD imports. `uv run lint-imports` enforces it.
- **COM (G1):** release in `finally` with `Marshal.ReleaseComObject`, never `FinalReleaseComObject`, no COM object off the STA thread.
- **Custody (ADR-022, ADR-046):** the job only saves or closes documents it owns, and never writes to an existing file.
- **Live tests:** scratch folder only. Do not close the owner's SOLIDWORKS. If `dotnet build` hits MSB3027, stop and ask the owner to close it.
- **Tolerances:** bounding box, center of mass and cylinder axis or radius ±0.01 mm; volume and surface area ±0.01%.
- **New error code:** `PART_VERIFICATION_FAILED`.
- **Python full check:** `uv run python scripts/generate_contracts.py --check`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run lint-imports`, `uv run pytest -m "not live"`.
- **C# check:** `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`.
- **Baseline to keep:** 2,712 Python and 241 C# tests pass today, plus the live results from Task 0.

## Review Focus

1. **A Chinese or other non-ASCII target path and a non-English SOLIDWORKS UI.** The part builds and verifies, because planes are found by order and paths survive JSON and COM unchanged. Tests in Task 6 (framing) and Task 12 (full chain).
2. **The default part template is missing, in inches, or unusual.** No template gives a clear message; an inch template still gives correct geometry; reordered planes or extra features fail clearly. Tests in Tasks 8 and 12.
3. **Two queued jobs naming the same target.** The first commits; the second fails with `AUTH_SOURCE_WRITE_NOT_ALLOWED` and never overwrites. Test in Task 9b.
4. **Numerically degenerate graphs:** a zero-length line, a tiny diameter, a loop that closes only within rounding, or a hole touching the edge. Each is rejected with a pointer, not left for SOLIDWORKS to fail on. Test in Task 4.
5. **The engineer interferes, or the folder or file changes, between build and publish.** The job fails, keeps the working file and names it, with no target written. Tests in Tasks 9b and 12.

---

### Task 0: Live drawing baseline

Frozen drawing live tests haven't been re-run since the freeze, so a later failure couldn't otherwise be attributed (F21).

**Files:**
- Modify: `docs/superpowers/review/2026-11-05-drawing-freeze.md`

- [ ] **Step 1: Run** `uv run pytest tests/live/ -m live -v` with the current add-in, on scratch files. Expected: matches the record of 5 passed, 1 skipped. A difference is reported to the owner, not fixed.
- [ ] **Step 2: Record** the results, commit, add-in build and SOLIDWORKS version in the freeze record.
- [ ] **Step 3: Commit:** `docs: record the live drawing baseline`.

### Task 1: Live spike on the SOLIDWORKS API

Everything later relies on these answers, and none has been verified.

**Files:**
- Create: `tests/live/spikes/PartChainSpike/` (a net48 console project, not in `ExecutionServer.sln`, using the same interop references as `ExecutionServer.Adapters`)
- Create: `tests/live/test_live_a14.py`
- Create: `docs/superpowers/review/2026-11-05-part-chain-spike.md`

**Interfaces:**
- Produces: the recorded answers used by Tasks 2, 7a, 7b, 8, 9a and 12.

- [ ] **Step 1: Write the spike** to attach to the running SOLIDWORKS out of process, working only in `%TEMP%\sw-mcp-spike\`, and touching only documents it creates. Build the plate from design 3 and print each answer below. Restore any setting it changes.
- [ ] **Step 2: Run it and record every answer in the spike document**, with the exact API call used:
  1. Sketch axes on `plane:front`, `plane:top`, `plane:right` in model coordinates, and which way a blind extrude and a blind cut go on each.
  2. Working calls and arguments for `sketch.create` (`AddToDB`), `FeatureExtrusion3` (or its current form) and `FeatureCut4`, including `through_all_both`, and selection with `Select4` marks.
  3. Whether `RefPlane` order gives front, top, right on this install, and how to read a plane's normal.
  4. `NewDocument` with `swDefaultTemplatePart`: result when the preference is empty; result with an inch template (does a metres-based API still give correct geometry?).
  5. `IFeature.GetID()` and `GetPersistReference3` before and after close and reopen (A2).
  6. `GetBodyBox` against the true box. `CreateMassProperty` volume, surface area and center of mass against computed values. How to list cylindrical faces with axis and radius.
  7. `CloseDoc` on a document with unsaved changes: does it prompt or discard (F4)? Is `QuitDoc` needed?
  8. How long a just-closed file stays locked against rename.
  9. Whether sketch and feature calls work on a document that isn't active.
  10. Whether `SaveAs4` with the silent option overwrites an existing file.
  11. The name format `FileCloseNotify` passes: title or full path.
  12. Whether reopening after close reads from disk, shown by changing nothing and comparing document state, and whether the document is reported closed first.
  13. Which part-document events report regen, save and destroy.
- [ ] **Step 3: Write and run** `test_a14_under_load` and `test_reconnect_immediately` through the pipe against the current add-in, using only `session.ping`, `document.open` and `document.close` on scratch files: 1,000 quick commands, one command while SOLIDWORKS is busy, and an immediate reconnect after a close. Record A14 and the reconnect result.
- [ ] **Step 4: Expected result:** every answer recorded. If a design assumption fails, stop and bring it to the owner before Task 2, with the design's fallback where it has one.
- [ ] **Step 5: Commit** the spike project, test and document: `test(live): record part chain API spike`.

### Task 2: Specification changes

**Files:**
- Modify: every row of design 11, namely `docs/architecture/feature-schema-guide.md` (5.7.4), `backend-operations.md` (6.5.2, 6.5.3), `cad-compiler.md` (6.7.4), `execution-engine.md` (8.3 rule 13 for D1, 8.4, 8.7), `verification-engine.md` (10.2), `project-store.md` (13.2.1, 13.2.3), `shared-ir-core.md` (3.4.5), `configuration.md` and `docs/api/mcp-interface.md` (`mcp.toolsets`), `docs/api/tool-contracts.md` (12.4.2, 12.4.4, 12.4.5, 12.5), `ADR-032`, `ADR-037`, `ADR-046`, `ADR-050` (the D1 exception, recorded as the owner's decision)
- Modify: `docs/specifications/README.md`, every topic header, `CHANGELOG.md` (version 1.30)
- Modify: `docs/specifications/roadmap.md` if the spike changed the MVP

**Interfaces:**
- Produces: the normative text later tasks are checked against.

- [ ] **Step 1: Check the spike against the design.** If an answer changes the design, update the design and this plan first.
- [ ] **Step 2: Write each change from design 11**, using the spike's values for 5.7.4 and the tables of design 8 for 8.4 and 13.2.3. Say in 12.4.4 that the four MVP tools ship before Phase 1c under ADR-057.
- [ ] **Step 3: Bump to v1.30** in `README.md` and every topic header. Add the changelog entry. Mark new rules **[Builder's call]**, except what the owner decided.
- [ ] **Step 4: Verify:** a `git grep -c` for the old v1.29 header string in `docs` returns nothing, and `uv run ruff format --check` passes.
- [ ] **Step 5: Commit:** `docs: specify the part chain MVP (spec v1.30)`.

### Task 3: Part Feature Graph schemas and model

**Files:**
- Create: `schemas/part-feature-graph/v0.json`, `schemas/part-feature-graph/features/{sketch,extrude,cut_extrude}.json`
- Create: `packages/cad-ir/src/cad_ir/part_feature_graph/{model.py,parse.py,planes.py}`
- Create: `tests/fixtures/schemas/part-feature-graph/` (valid: the plate from design 3; invalid: one per rule below)
- Test: `packages/cad-ir/tests/test_part_feature_graph.py`

**Interfaces:**
- Consumes: `validate_against_schema`, `IssueReport` from `cad_ir.core`.
- Produces:
  - `PART_SCHEMA_ID: Final[str]`
  - Frozen dataclasses `Line(start, end)`, `Circle(center, diameter)`, `SketchNode(plane, entities, dependencies, display_name, realizes)`, `EndCondition(type, depth)`, `SolidNode(type, profile, end_condition, dependencies, display_name, realizes)`, `PartGraph(id, schema_version, units, origin, nodes)`, where `nodes: Mapping[str, SketchNode | SolidNode]`
  - `parse_part_graph(doc: JsonValue) -> PartGraph | IssueReport`
  - `plane_axes(plane: str) -> PlaneAxes`, which maps sketch `(x, y)` and extrude depth to model XYZ using the 5.7.4 values. Only `cad-verification` uses it.

- [ ] **Step 1: Write failing tests:**
  - `test_plate_parses`: `nodes` has 4 entries and `cut_holes.end_condition.type == "through_all_both"`.
  - `test_unknown_field_rejected`: `suppressed: true` gives `IR_SCHEMA_INVALID` with a pointer to that field.
  - `test_blind_needs_depth` and `test_through_all_has_no_depth`.
  - `test_model_matches_schema`: every schema property of each node type has a dataclass field, and the reverse.
  - `test_examples_within_budget`: each feature file's example is at most 400 tokens (UTF-8 bytes of compact JSON ÷ 4, as 12.4.5 does).
- [ ] **Step 2: Run:** `uv run pytest packages/cad-ir/tests/test_part_feature_graph.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Write the schemas** per design 5 with `additionalProperties: false`, then the model and `parse_part_graph`, following `cad_ir/drawing_intent/parse.py`. Run `uv run python scripts/generate_contracts.py` to embed the schemas.
- [ ] **Step 4: Run** the test file and `tests/contract/test_schema_fixtures.py`. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(ir): add Part Feature Graph schemas and model`.

### Task 6: IPC contracts and the backend port

Runs before the compiler, so plans are checked against real operation schemas.

**Files:**
- Create: `schemas/ipc/ops/{part.create,sketch.create,feature.create}.json`
- Modify: `schemas/ipc/v0.json` (`part.measure`, `instance_id` on `document.open`'s result), `schemas/ipc/ops/document.open.json`, `schemas/common/errors.json` (`PART_VERIFICATION_FAILED`), `tests/contract/test_generated_contracts.py`, generated files via the generator
- Modify: `packages/cad-protocol/src/cad_protocol/backend.py`, `replay.py`
- Modify: `packages/cad-application/src/cad_application/ports.py`, `testing/fakes.py`
- Modify: `apps/core-service/src/core_service/discovery.py`, `reconcile.py`
- Test: `tests/contract/test_part_ops.py`, `tests/fixtures/schemas/ipc/`, `tests/integration/test_backend_lifecycle.py`

**Interfaces:**
- Produces on `Backend`: `measure_part(self, document: str, *, meta: Meta | None = None) -> JsonValue` and `close(self) -> None`. `IpcBackend.close` already exists; the port gains it.
- Produces on the fake backend: scripted measurements and per-op results for job tests.

- [ ] **Step 1: Write failing tests:**
  - The fields in the design 7 table validate, and `part.measure` carries raw SI fields.
  - `test_measure_round_trip` through a synthetic transcript.
  - `test_failed_handshake_closes`: an `IpcError` from `IpcBackend(client)` closes the client.
  - `test_failed_reconcile_closes`: the backend closes, and the next `acquire` works.
  - `test_reconnect_waits`: a connect during the add-in's gap succeeds within the bound, using the Task 1 result.
  - `test_non_ascii_round_trip`: `D:\零件\板.SLDPRT` survives a Python-to-C# framing transcript unchanged.
  - The new error code appears in generated Python and C#.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Write the schemas, run the generator, add the port methods** to replay and fakes. Fix both closing paths. Add the bounded reconnect wait.
- [ ] **Step 4: Full check and C# check.** Expected: all pass, with existing transcripts unchanged.
- [ ] **Step 5: Commit:** `feat(protocol): add part operations, part.measure and Backend.close`.

### Task 4: Compiler

**Files:**
- Create: `schemas/execution-plan/v0.json`, `packages/cad-compiler/defaults/0.1.0.json`
- Create in `packages/cad-compiler/src/cad_compiler/`: `api.py`, `profile.py`, `registry.py`, `validator/semantic.py`, `graph/analyze.py`, `lowering/lower.py`, `planner/plan.py`
- Test: `packages/cad-compiler/tests/`, golden file `tests/fixtures/plans/plate_4h.json`

**Interfaces:**
- Consumes: `parse_part_graph`, `PartGraph`, `BundleManifest`, the schemas from Task 6. Not `plane_axes`.
- Produces:
  - `CapabilityProfile.from_session(session: HelloResult) -> CapabilityProfile`, with `operations: frozenset[str]`, `coverage`, and `hash: str` computed inside. Tests build one from a `HelloResult`.
  - `CompileContext(compiler_version: str, profile: CapabilityProfile, defaults: Mapping[str, JsonValue])`
  - `CompileInput(manifest: BundleManifest, documents: Mapping[str, JsonValue])`, keyed by pinned `DocumentRef` text
  - `CompileResult(plan: JsonValue | None, plan_hash: str | None, diagnostics: tuple[Diagnostic, ...])`, where `Diagnostic` is 3.4.7 plus `stage`
  - `compile_bundle(source: CompileInput, ctx: CompileContext) -> CompileResult`
  - `validate_graph(graph: PartGraph) -> tuple[ValidationIssue, ...]` (semantic only, used by `validate_part_graph`)
  - `build_order(graph: PartGraph) -> tuple[str, ...]`
  - `WORKING: Final = "$working"`, the plan's document symbol

- [ ] **Step 1: Write failing tests:**
  - `test_build_order_plate` equals `("sketch_base", "extrude_base", "sketch_holes", "cut_holes")`.
  - `test_cycle_rejected` gives `IR_CYCLE`.
  - `test_rules` is parametrized over: open loop, self-intersecting loop, overlapping circles, a hole outside the profile, a hole on a different plane, two extrudes, several circles as an extrude's profile, a cut before the extrude, `units: in`, a missing profile, a profile that is not a sketch. Each gives the right code and pointer, and two errors in one graph are both reported.
  - `test_degenerate_rejected` (Review Focus 4): zero-length line, diameter below 0.01 mm, a loop whose ends miss by more than the 3.4.3 quantum, and a hole tangent to the edge are all `IR_RULE_VIOLATED`.
  - `test_plan_matches_golden`: operations in order `part.create`, `sketch.create`, `feature.create`, `sketch.create`, `feature.create`. `document` is `$working`, `feature.create.profile` is the sketch's node ID, sketch coordinates are 2D, and each op's params validate against its Task 6 schema.
  - `test_revision_does_not_change_body`: the same content at revisions 1 and 2 gives identical `operations`, while the pinned bundle differs.
  - `test_determinism`: same hash twice in one process and from a fresh subprocess (15.6).
  - `test_profile_hash_changes_with_session` and `test_profile_includes_coverage`.
  - `test_unsupported_plane` gives `COMPILE_UNSUPPORTED_FEATURE`.
  - `test_missing_operation` gives `BACKEND_CAPABILITY_MISSING`.
  - `test_plan_validates_against_schema`.
- [ ] **Step 2: Run:** `uv run pytest packages/cad-compiler -v`. Expected: FAIL.
- [ ] **Step 3: Implement** each 6.7 stage as `run(input, context) -> StageResult(output, diagnostics, needs)`. Postconditions: `feature_exists`, `feature_status_ok`, `rebuild_ok` on each solid; `entity_count` on each sketch. A `verification_points` entry after each solid feature. Provenance: compiler version, stage versions, profile hash. Use `content_hash` for the plan hash.
- [ ] **Step 4: Run** the tests and `uv run lint-imports`. Expected: PASS, 5 contracts kept.
- [ ] **Step 5: Commit:** `feat(compiler): compile Part Feature Graphs to Execution Plans`.

### Task 5: Verification core

**Files:**
- Create: `packages/cad-verification/src/cad_verification/part.py`
- Test: `packages/cad-verification/tests/test_part.py`

**Interfaces:**
- Consumes: `PartGraph`, `plane_axes`.
- Produces:
  - `ExpectedGeometry(solid_body_count: int, bbox_mm: Box, volume_mm3: float, surface_area_mm2: float, center_of_mass_mm: Point3, cylinders: tuple[ExpectedCylinder, ...], features: tuple[ExpectedFeature, ...])`
  - `expected_geometry(graph: PartGraph) -> ExpectedGeometry`
  - `CheckResult(requirement: str, measured: JsonValue, expected: JsonValue, tolerance: float | None, passed: bool, method: str)`
  - `compare(expected: ExpectedGeometry, measured: JsonValue, feature_ids: Mapping[str, str]) -> tuple[CheckResult, ...]`, where `measured` holds raw SI values and this function converts them

- [ ] **Step 1: Write failing tests:**
  - `test_plate_expected`: count 1, volume `approx(57989.38, abs=0.01)`, box size `(100, 60, 10)`, 4 features, 4 cylinders of radius 4, surface area and center of mass from hand-calculated values.
  - `test_blind_cut_expected`: a Ø10 blind cut 4 mm deep removes π × 25 × 4, moves the center of mass, and adds 2π × 5 × 4 to the area.
  - `test_clean_measurement_all_pass`.
  - `test_si_conversion_literals`: `5.798938e-5` m³ reads as 57,989.38 mm³.
  - `test_missing_hole_fails_volume`.
  - `test_moved_holes_fail` (F1): symmetric holes at (±20, ±10), with the same volume and box, fail `cylinders`.
  - `test_same_area_profile_fails` (F1): a different profile with equal area and box fails.
  - `test_within_tolerance_passes` and `test_just_outside_fails` for every tolerance in Global Constraints.
  - `test_rebuild_error_fails`, `test_extra_body_fails`, `test_extra_feature_fails`, `test_sick_feature_fails`, `test_missing_feature_fails`, `test_wrong_type_with_matching_id_fails`.
  - `test_every_comparison_runs`: three problems give three failed results.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Implement** per design 9. `compare` never stops at the first failure.
- [ ] **Step 4: Run** and `uv run lint-imports`. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(verification): compute and compare expected part geometry`.

### Task 7a: Dispatch and ownership

**Files:**
- Create: `apps/execution-server/ExecutionServer.Core/Ownership/DocumentOwnershipTable.cs`, `ExecutionServer.Core/Dispatch/OperationRouter.cs`
- Modify: `ExecutionServer.AddIn/SwAddin.cs` (register handlers in the router; `document.open`, `document.close`, `document.save`; `:544`)
- Create: `ExecutionServer.Adapters/Documents/DocumentOps.cs`, which calls `DrawingCreationAdapter.SaveDocument` unchanged for drawings
- Modify: `schemas/ipc/v0.json` (additive `failed_operations`, then regenerate), `ExecutionServer.Core/Ledger/OperationLedger.cs`, `ExecutionServer.Core/Ipc/OpsBatchRunner.cs`, and the recovery step in `cad_application` that records completed operations (8.7, 13.2.3)
- Test: `ExecutionServer.Tests/Ownership/DocumentOwnershipTableTests.cs`, `ExecutionServer.Tests/Dispatch/OperationRouterTests.cs`

**Interfaces:**
- Produces (CAD-free):
  - `OperationRouter.Register(string op, handler)`, `Route(document, operation, ct)`, and `Operations`, which feeds `HelloResult`
  - `DocumentOwnershipTable.Record(string path, string jobId, bool owned, string instanceId, string? previousActive)`
  - `OwnershipDecision CheckSave(string path, string? targetPath, string? jobId)`
  - `OwnershipDecision CheckClose(string path, string? jobId)`
  - `string? PreviousActive(string path, string jobId)`
  - `Forget(string path)`
  - Paths compare case-insensitively after normalizing.

- [ ] **Step 1: Write failing tests:**
  - `SaveOwnedPart_Allowed`; `SavePartOfOtherJob_Refused`; `SaveUnknownPart_Refused`; `SaveOwnedPartToOtherPath_Refused`, each refusal with `AUTH_SOURCE_WRITE_NOT_ALLOWED`.
  - `SaveUnknownDrawing_Allowed`, including a title and a `target_path`, the frozen flow.
  - `CloseUnownedPart_Refused`; `CloseOwnedPart_ReturnsPreviousActive`.
  - `CloseBorrowedDrawingOfThisJob_Refused`; `CloseUnlistedDrawing_Allowed`.
  - `DeadJobEntry_GrantsNothing`: an entry for job A gives job B no rights.
  - `UnknownOperation_IsError`, with `BACKEND_CAPABILITY_MISSING`, never recorded in the ledger.
  - `RouterOperations_MatchHello`: all 13 current operations are registered.
  - `NonAsciiPath_Matches` for `D:\零件\板.SLDPRT`.
  - Ledger (8.7, closes K17): `FailureWithEffectApplied_IsRecorded`; `FailureWithEffectUnknown_IsRecorded`; `FailureWithEffectNone_IsNotRecorded`; `FailureWithoutEffect_IsNotRecorded`, the frozen drawing flow; `UnexpectedException_IsRecordedAsUnknown`; `RepeatOfRecordedFailure_ReturnsDuplicateWithOriginalError_AndDoesNotRun`; `RecordedFailure_NotInOperationIds_ListedInFailedOperations`.
  - Python: `test_recovery_records_failed_operations` gives `op_result` with `ok: false` and `recovered: true`; a transcript with no `failed_operations` still parses.
- [ ] **Step 2: Run** the C# check and confirm FAIL.
- [ ] **Step 3: Implement.** `document.open` checks whether the document is already open, reports true `owned`, returns `instance_id`, and passes the read-only flag. Part saves and closes find the document by path, never `ActiveDoc`. Drawings keep today's lookup. Close follows spike answer 7.
- [ ] **Step 4: C# check, then the full check.** Expected: PASS. Ask the owner to close SOLIDWORKS, then run `dotnet build apps/execution-server/ExecutionServer.sln`.
- [ ] **Step 5: Run** the Task 0 live suite. Expected: same as the baseline. Report any difference rather than editing frozen code.
- [ ] **Step 6: Commit:** `fix(addin): move dispatch to Core and enforce document ownership`.

### Task 7b: Events and instance IDs

**Files:**
- Modify: `ExecutionServer.AddIn/Events/DocumentEventMonitor.cs`, `ExecutionServer.Core/Events/DocumentEventMonitor.cs`, `ExecutionServer.Core/Ledger/OperationLedger.cs` callers in `SwAddin.cs`
- Test: `ExecutionServer.Tests/Events/`, `tests/live/test_live_part_events.py`

**Interfaces:**
- Consumes: `DocumentOwnershipTable.Forget`, `OperationLedger.ForgetDocument`, spike answers 11 and 13 (`FileCloseNotify` never fires for an API close; use `DestroyNotify2`).
- Produces:
  - `document.event` with `regen` (`RegenNotify`, `RegenPostNotify`), `save` (`FileSavePostNotify`, not `FileSaveNotify`) and `close` (`DestroyNotify2`) for a part document the table lists, tagged with `_meta` when the job caused it.
  - `Forget` and `ForgetDocument` on `DestroyNotify2`, and a lazy `GetOpenDocumentByName(fullPath)` check before a table entry is trusted (a close the engineer did in the UI).

- [ ] **Step 1: Write failing tests:** `UntaggedSaveOnOwnedPart_RaisesEvent`; `EventDuringCommand_IsTagged`; `Close_ForgetsTableAndLedger` (on `DestroyNotify2`); `StaleEntry_DroppedWhenDocumentGone` (the lazy path check); `PathNormalizes_ForTableLookup`. `FileCloseNotify` is not relied on (spike answer 11). Live: saving, editing or closing an open scratch part by hand through a separate COM call produces an untagged event.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Implement.** Subscribe per document when a part enters the table and release on `DestroyNotify2`, following G1. Mark the job's own calls with a flag, since every API call raises regen events (spike answer 13).
- [ ] **Step 4: C# check, build (SOLIDWORKS closed by the owner), then the live test and Task 0 suite.** Expected: PASS, same as the baseline.
- [ ] **Step 5: Commit:** `feat(addin): report engineer activity on working parts`.

### Task 7c: Dispatcher and capability table

Added by owner decision, 2026-11-05, from the [adapter roadmap](../../plans/solidworks-adapter-roadmap.md) A1 ([ADR-059](../../adr/ADR-059-com-sta-execution.md) threading and queue rules, [ADR-062](../../adr/ADR-062-version-isolation.md)). **Run it after Task 7a and before Task 7b,** because a wrong thread would invalidate later live results. It also brings the add-in host in line with the release rule in G1 (owner decision, 2026-11-05).

**Files:**
- Create: `ExecutionServer.AddIn/Dispatch/ControlSynchronizationContext.cs` (hidden WinForms control, handle forced, `BeginInvoke`), `ExecutionServer.AddIn/Diagnostics/SessionProbe.cs`
- Create: `ExecutionServer.Core/Versions/SolidWorksVersion.cs`, `ExecutionServer.Core/Versions/CapabilityTable.cs`
- Modify: `ExecutionServer.AddIn/ExecutionServer.AddIn.csproj` (framework reference to `System.Windows.Forms`, AddIn only), `ExecutionServer.AddIn/SwAddin.cs` (`:95-100` context, `:104-107` version, `:129` UI language, `:131` capabilities, from the router and table), `ExecutionServer.Core/Dispatch/UIThreadDispatcher.cs`, `ExecutionServer.Core/Ipc/IpcSession.Commands.cs`, `ExecutionServer.Core/Pipe/NamedPipeServer.cs` (outgoing frame queue)
- Test: `ExecutionServer.Tests/Dispatch/UIThreadDispatcherTests.cs`, `ExecutionServer.Tests/Versions/CapabilityTableTests.cs`, `ExecutionServer.Tests/Pipe/NamedPipeServerTests.cs`, `tests/live/test_live_dispatch.py`

**Interfaces:**
- Produces (CAD-free): `SolidWorksVersion.Parse(string revision)`, which fails on a value it cannot read; `CapabilityTable.For(SolidWorksVersion)` with `Support`, `Names` and `Has(string)`.
- `session.hello` gains the real version and UI language. If either cannot be read, the add-in reports that and answers `BACKEND_VERSION_UNSUPPORTED`; it never uses a default.

- [ ] **Step 1: Write failing tests:**
  - `CommandPostedWhileOneRuns_RunsAfterwards`: no queued command is stranded (F21).
  - `ReentrantDrain_IsRefusedAndNothingIsLost`.
  - `DrainOnWrongThread_RunsNothingAndReports`.
  - `ResponseWrite_DoesNotBlockTheCommandThread`, with a stalled sink.
  - `Frames_KeepTheirOrder`, and `Close_FlushesOrFailsQueuedFrames`.
  - `Parse_RealRevisions`: `33.0.0` and a three-part service pack keep every segment; null, empty and malformed values fail.
  - `Support_FollowsAdr045`: supported, newer service pack with a warning, older and newer major refused.
  - `HelloLists_OnlyRegisteredOperations`.
- [ ] **Step 2: Run** the C# check and confirm FAIL.
- [ ] **Step 3: Implement.** Remove the base `SynchronizationContext` fallback. Refuse to start the server if `ConnectToSW` is not on an STA thread. Re-post when a command ends if the queue is not empty. Send all pipe writes through the pipe side, never from the UI thread. Stop releasing `ISldWorks` (`SwAddin.cs:255`) and `IModelDoc2` (`:434`, or wherever Task 7a moved it), per G1. Frozen drawing adapters are not changed; if shared code forces a change there, ask the owner first.
- [ ] **Step 4: C# check, build (SOLIDWORKS closed by the owner), then the live test on a throwaway instance:** log the thread ID, apartment state and dispatch path once per session, and post commands during a running one.
- [ ] **Step 5: Run** the Task 0 live suite. Expected: same as the baseline. Report any difference rather than editing frozen code.
- [ ] **Step 6: Commit:** `fix(addin): keep commands on the STA thread and report real capabilities`.

### Task 8: Part adapters

**Files:**
- Create: `ExecutionServer.Adapters/Parts/{PartCreationAdapter,SketchAdapter,FeatureAdapter,PartMeasureAdapter}.cs`
- Create: `ExecutionServer.Core/Parts/PartUnits.cs` (mm to metres, CAD-free)
- Create: `ExecutionServer.Adapters/Native/{ComScope,DocumentLocator}.cs` (G1, ADR-059; full-path lookup only, 8.9.8)
- Modify: `SwAddin.cs` (register operations, the `part.measure` capability, the real UI language at `:129`), the command path that handles `drawing.snapshot` (add `part.measure` beside it)
- Test: `ExecutionServer.Tests/Parts/PartUnitsTests.cs`; `tests/live/test_live_part_ops.py`

**Interfaces:**
- Consumes: the schemas of Task 6, the router and table of Task 7a, the spike's calls.
- Produces: operations and the command that behave per design 7. From ADR-064: `document.rebuild`, and `observation` in each creating operation's result (8.9.3), T0 facts only. `rebuild` in `part.measure` follows K19.

- [ ] **Step 1: Write failing tests:**
  - `PartUnits` conversions against literal values.
  - Live, on scratch: `test_build_plate_by_ops`: the five operations by hand on a new file give the expected raw values within tolerance, with `f<id>` IDs and four cylinders.
  - `test_missing_template_is_clear` (Review Focus 2): a `template` param pointing at a missing file gives `FILE_NOT_FOUND` naming `part.template`. Never change the owner's preference.
  - `test_unset_template_is_clear`: with no `template` param and `part.template` unset (or its file missing), the job-level resolution fails with `CONFIG_INVALID` or `FILE_NOT_FOUND`, `details.setting: part.template`, and SOLIDWORKS's own default template is never used.
  - `test_build_plate_with_owner_and_installed_templates`: the plate builds and measures the same with the owner's `D:\01_Data\ZZ_EPG Drawing templates\ISO-mm.prtdot` and the installed `gb_part.prtdot`.
  - `test_blind_cut_goes_into_body`: a blind cut on each of the three planes changes the volume by the expected amount (`Dir=true`, spike answer 4).
  - `test_inch_template_builds_mm` (Review Focus 2), with an inch template created in the scratch folder.
  - `test_part_create_refuses_existing_file`.
  - `test_null_feature_fails`: a cut with an empty profile fails with `BACKEND_REBUILD_ERROR`, not a false result.
  - `test_wrong_plane_normal_fails`, if the spike found a way to make such a template; otherwise a unit test around the normal check.
  - `test_ops_work_on_inactive_document`: spike answer 9 showed feature calls need no active document, so the adapters do no active-document check; the test builds on a document that is not active and leaves the active document unchanged.
  - `test_settings_restored`: inference and graphics updates are back to their earlier values after each operation, including a failing one.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Implement per design 7's rules,** using the spike's calls: find documents by full path only (R2); `IFeature.Select2` and `Select4` for selection, never `SelectByID2`; `Dir=true` for a blind cut; `UseSystemUnits=true` for `IMassProperty`; `part.create` refuses an existing path itself, since silent `SaveAs4` overwrites. Results are read back from SOLIDWORKS. `part.create` records ownership and returns `instance_id`, `previous_active` and `template`. Each adapter handles `CancellationToken` between steps and releases COM in `finally`.
- [ ] **Step 4: Build (SOLIDWORKS closed by the owner), register, reopen, and run** `uv run pytest tests/live/test_live_part_ops.py -m live -v`, then the Task 0 suite. Expected: PASS, same as the baseline.
- [ ] **Step 5: Commit:** `feat(addin): build and measure parts`.

### Task 9a: Store, journal and recovery

**Files:**
- Modify: `store/journal_records.py`, `store/journal.py`, `store/job_records.py`, `store/file_store.py`, `ports.py`, `paths.py`, `schemas/store/v0.json`, `testing/memory_fs.py`, `core_service/os_fs.py`, and the `recover` call in `jobs/engine.py`
- Test: `packages/cad-application/tests/test_part_store.py`, `tests/integration/test_part_recovery.py`, `apps/core-service/tests/test_rename_new.py`

**Interfaces:**
- Produces:
  - `DocumentAction` gains `create`; new records `PublishIntentRecord(ts, job_id, path, fingerprint)` and `PublishedRecord(ts, job_id, path)`
  - `recover(store, clock, read_fingerprint: Callable[[str], str | None])`
  - `FileSystem.rename_new(source: str, target: str) -> None` (raises `FileExistsError`; write-through on the OS implementation)
  - `authorize(..., expect="new_file")`
  - `Store.put_part_revision(ref: str, doc: JsonValue, expected_revision: int | None) -> str | StoreError`, `Store.put_plan(plan_hash: str, plan: JsonValue) -> bool` (False when reused), `Store.get_part_revision(ref: str)`, `Store.put_part_record`
  - `OpVerifiedRecord` (ADR-064, 13.2.3)
  - `JobRecord.part_result: JsonValue | None`, holding `path`, `fingerprint`, `checks`, `measured`, `feature_ids`, `template`

- [ ] **Step 1: Write failing tests:**
  - `test_action_round_trip`: `create` survives writing and reading, and an unknown action is an error, not `open`.
  - `test_unknown_documents_include_create`.
  - `test_old_job_json_loads`: a v0 record with no new field still parses.
  - `test_rename_new_refuses_existing`, against both file systems.
  - `test_new_file_authorize`: missing parent, existing file, vault, and existing `expect` behaviour unchanged.
  - `test_plan_reuse`: writing the same plan twice returns False the second time and doesn't raise.
  - `test_revision_rules`: new ID gives 1; same content reuses it; changed content needs `expected_revision`, else `REV_CONFLICT`.
  - `test_crash_points` is parametrized over: before `part.create`, after it, after an operation, after `publish_intent` with no rename, after the rename with no `published`, before COMMITTED. Each recovers to FAILED with `EXEC_INTERRUPTED`, lists the working part as `unknown` where it applies, and never resends.
  - `test_published_unconfirmed`: a matching target adds the warning and is not adopted; a differing or missing target adds none.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Implement.** Update `_action`, the schema enum and recovery together. Existing `check_drawing` journal lines must read back unchanged.
- [ ] **Step 4: Full check.** Expected: PASS, including every `check_drawing` test.
- [ ] **Step 5: Commit:** `feat(store): add part records and publication to the journal`.

### Task 9b: The `plan` job

**Files:**
- Create: `packages/cad-application/src/cad_application/jobs/plan_job.py`, `jobs/part_files.py`
- Modify: `jobs/engine.py` (dispatch by spec type; close the backend in `run_next` after the final state), `jobs/model.py` (`PlanSpec`, record builder), `jobs/handle.py` (spec type)
- Test: `tests/integration/test_plan_job.py`, transcripts `tests/fixtures/ipc/plan_*.jsonl`

**Interfaces:**
- Consumes: `compile_bundle`, `CapabilityProfile.from_session`, `expected_geometry`, `compare`, `feature_contracts` and `evaluate` (ADR-064, written first in `cad_verification/api/`), `Backend.measure_part`, `Backend.close`, everything from Task 9a.
- Produces:
  - `PlanSpec(authorized: Authorized, target_path: str, ref: str)`. The job loads the graph from the store by `ref`.
  - `JobEngine.submit(spec: CheckDrawingSpec | PlanSpec, request_id: str)`
  - `working_path(target: str, job_id: str) -> str`, `failed_path(...)`, `partial_path(...)`

- [ ] **Step 1: Write failing tests:**
  - `test_plate_commits`: fake backend, states PLANNED → VALIDATED → EXECUTING → VERIFYING → COMMITTED; target exists; `part_result` holds passes; a part record exists.
  - `test_binds_symbols`: the operations sent carry the working path and the real `feature_id`, one operation per batch, with `batch_sent` journalled before each send and `document` `create` before `part.create`.
  - `test_measures_twice`: once before close and once after a read-only reopen.
  - `test_same_instance_on_reopen_fails` (F6) and `test_still_open_after_close_fails`.
  - `test_fingerprint_change_fails` (F6): the working file changes between reopen and publish; no target.
  - `test_publish_rechecks_path` (F6): a folder now resolving outside the root fails; no target.
  - `test_publish_order`: `publish_intent` before the rename, `published` after, then COMMITTED.
  - `test_cancel_after_publish_intent_has_no_effect` and `test_cancel_before_publish_intent_aborts`.
  - `test_failed_contract_stops_the_job` (ADR-064): a wrong type or sick feature ends the job with `PROPOSED_FEATURE_VERIFICATION_FAILED`, names the node, sends nothing further, and journals `op_verified` first. A feature warning does the same (K22).
  - `test_wrong_volume_fails`: `PART_VERIFICATION_FAILED`, `details` lists the check, no target, `.failed` present and named.
  - `test_reopen_mismatch_fails`: only the second measurement is wrong.
  - `test_op_error_fails_and_keeps_file`.
  - `test_cancel_removes_working`, with `changes` naming the file; `test_keep_partial_renames`.
  - `test_backend_lost_leaves_files` and lists `unknown`, with no close sent; the same for `BACKEND_UI_BLOCKED`, `EXEC_TIMEOUT`, `EXEC_INTERRUPTED_BY_USER`.
  - `test_foreign_event_fails`: an untagged regen, save or close on the working part fails the job.
  - `test_two_jobs_same_target` (Review Focus 3): the first commits; the second fails with `AUTH_SOURCE_WRITE_NOT_ALLOWED` and the first's file is unchanged.
  - `test_rename_blocked` (Review Focus 5): a persistent lock or missing folder at rename gives FAILED, working file kept and named, no target.
  - `test_close_after_final_state` (F7): `close` is called after the final state, a failing `close` only logs, and `close` runs for `check_drawing` too.
  - `test_second_job_reconnects` (F7): the first job's backend closed before the second `acquire`.
  - Recorded-style transcripts for these paths replay through the real `IpcBackend`.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Implement per design 8.** `plan_job.py` has its own `_Run`, modelled on `check_drawing.py`'s structure (validate, execute, verify, stop rules, notifications), with shared helpers extracted only into new modules. The rename retries within a bounded wait through the `Clock` port, using spike answer 8. No resend ever (8.3 rule 8).
- [ ] **Step 4: Full check.** Expected: PASS, including every `check_drawing` test.
- [ ] **Step 5: Commit:** `feat(application): add the plan job`.

### Task 10: MCP tools

**Files:**
- Create: `schemas/mcp/{apply_part_graph,validate_part_graph,list_feature_types,get_feature_schema}.json`
- Create: `packages/cad-application/src/cad_application/tools/{apply_part_graph,validate_part_graph,list_feature_types,get_feature_schema}.py`
- Modify: `tools/registry.py`, `tools/get_execution_status.py`, `schemas/mcp/get_execution_status.json`, `tests/contract/test_tool_table.py` (`SHIPPED_TOOLS`: the 1a phase plus these four names)
- Test: `tests/contract/test_part_tools.py`

**Interfaces:**
- Consumes: `parse_part_graph`, `validate_graph`, `build_order`, `expected_geometry`, `JobEngine.submit(PlanSpec)`, `Store.put_part_revision`.
- Produces: tools per design 10. `validate_part_graph` needs no SOLIDWORKS.

- [ ] **Step 1: Write failing tests:**
  - `test_apply_plate_queues`: `execution_id`, `queued_position`, `document` as a pinned ref.
  - `test_apply_bad_graph_no_job`: `IR_RULE_VIOLATED`, with issues and no job.
  - `test_apply_existing_target_denied`: `AUTH_SOURCE_WRITE_NOT_ALLOWED`.
  - `test_apply_missing_parent`, `test_apply_outside_roots`, `test_apply_wrong_suffix`, `test_apply_in_vault_denied`.
  - `test_apply_long_path_denied`: the working path would reach 260 characters.
  - `test_same_graph_same_revision`; `test_changed_graph_without_revision_conflicts`; `test_changed_graph_with_revision_next`.
  - `test_validate_returns_expected`: `valid`, `build_order`, `expected.volume_mm3`.
  - `test_list_types`: exactly three types.
  - `test_schema_unknown_type`.
  - `test_status_has_part_result`.
  - `test_summaries_fit`: under 200 characters, and `apply` names the job.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Implement,** following `tools/check_drawing.py`. Keep descriptions within 12.4.1's limits.
- [ ] **Step 4: Full check.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(tools): add part graph tools`.

### Task 11: Runtime and the MCP front-end

**Files:**
- Create: `apps/core-service/src/core_service/__main__.py`, `apps/mcp-server/src/mcp_server/__main__.py`
- Modify: both `pyproject.toml` files (`[project.scripts]`: `sw-mcp-core`, `sw-mcp-mcp`)
- Rewrite: `apps/mcp-server/src/mcp_server/server/app.py` on the SDK's low-level server; `server/__init__.py`
- Rewrite: `apps/mcp-server/tests/test_mcp_front_end.py`, which uses `McpServer` and `handle_message`
- Modify: `apps/core-service/src/core_service/server/pipe_host.py` (user-only pipe ACL, `hmac.compare_digest`, toolset filter on `list_tools` and calls), `cad_application/config/merge.py:198`, `settings.py:39` (`mcp.toolsets` default `["core"]`), `schemas/config/v1.json` and the settings model (`part.template`), and config tests expecting the old default
- Create: `docs/development/setup.md`
- Test: `tests/contract/test_mcp_list.py`, `tests/e2e/test_core_process.py`

**Interfaces:**
- Consumes: `CoreService`, `PipeHost`, `NamedPipeBackendProvider`, `CorePipeClient`.
- Produces: `sw-mcp-core` and `sw-mcp-mcp` commands. `CoreService.call_tool` stays unfiltered.

- [ ] **Step 1: Write failing tests:**
  - `test_list_matches_contracts`: `tools/list` equals the contract files for the configured toolsets, with `inputSchema`, `outputSchema` and all four annotations.
  - `test_default_hides_drawing_tools`: `check_drawing` absent by default, present with `drawing` set.
  - `test_disabled_tool_refused`: calling `check_drawing` over the pipe with the default toolsets gives a protocol error, and `CoreService.call_tool` in process still works.
  - `test_call_maps_result`: `summary` to text, envelope to `structuredContent`; a failed envelope has `isError: true`.
  - `test_unknown_tool_protocol_error`: `-32602`.
  - `test_stdio_utf8`: Chinese text through a real front-end process, under a non-UTF-8 console code page.
  - `test_core_start_stop`: real process, replay provider, session file written then removed.
  - `test_second_core_refused`.
  - `test_front_end_starts_core`.
  - `test_bad_token_closed`.
  - `test_part_template_setting`: `part.template` defaults to empty; it is read from the user file, ignored with a warning in a project file and in the environment (`SWMCP_PART__TEMPLATE`); a relative path or one not ending in `.prtdot` is `CONFIG_INVALID` naming the key; a path that does not exist is accepted at load.
- [ ] **Step 2: Run** and confirm FAIL.
- [ ] **Step 3: Implement.** The SDK negotiates the protocol revision (ADR-044). The core's job thread and pipe host start together. Write `setup.md`: build and register the add-in, `access.allowed_roots`, and the `mcpServers` entry for Claude.
- [ ] **Step 4: Full check.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(runtime): add entry points and move the front-end to the MCP SDK`.

### Task 12: Live acceptance

**Files:**
- Create: `tests/live/test_live_part_chain.py`
- Create: a test-only provider in that file that wraps the backend and alters a depth in transit
- Create: recorded transcript `tests/fixtures/ipc/plan_plate_recorded.jsonl`
- Create or modify: `docs/specifications/assumptions.md`

**Interfaces:**
- Consumes: everything above, through `CoreService.call_tool` with `NamedPipeBackendProvider`.

- [ ] **Step 1: Write the tests,** all on scratch folders, covering design 12 items 8 to 12f:
  - `test_plate_end_to_end`: reach COMMITTED, then open the target in a separate read-only step and measure it again.
  - `test_wrong_plan_fails`: the test provider changes depth to 9 in transit; the job ends FAILED, the target absent, the `.failed` file present.
  - `test_second_job_same_core`.
  - `test_open_dirty_document_untouched`: a scratch document open and unsaved stays open, unsaved and active.
  - `test_unknown_op_fails_batch`.
  - `test_engineer_interference`, parametrized: a separate COM call switches, edits, saves or closes the working part mid-job. The job fails with no target. Switching applies only if spike answer 9 says it matters.
  - `test_reopen_is_new_instance`.
  - `test_template_with_reordered_planes` and `test_template_with_extra_feature`: both fail clearly.
  - `test_core_killed_mid_job`: `taskkill` the core process mid-job; the target stays absent, the new core reports the job interrupted, and the next job works once the working part is dealt with.
  - `test_non_ascii_path`: a target under a folder named `零件`.
- [ ] **Step 2: Run:** `uv run pytest tests/live/test_live_part_chain.py -m live -v`. Expected: PASS. A failure here is a defect to diagnose, not a test to weaken.
- [ ] **Step 3: Record the transcript** and add a replay test. Record A2 and A14 outcomes only in `docs/specifications/assumptions.md`.
- [ ] **Step 4: Run** the Task 0 suite (item 12f). Expected: same as the baseline.
- [ ] **Step 5: Full check and C# check.**
- [ ] **Step 6: Commit:** `test(live): verify the part chain end to end`.

### Task 13: The run from Claude

The finish line is the owner's, so an agent cannot complete it alone.

**Files:**
- Modify: `HANDOFF.md`, `docs/specifications/roadmap.md`, `docs/development/setup.md` for anything the run exposed

- [ ] **Step 1: Set up per `setup.md`** with the owner, from a clean state.
- [ ] **Step 2: The owner asks Claude, in plain language,** for the plate in a scratch folder. Expected: Claude uses `list_feature_types`, `get_feature_schema`, `validate_part_graph` and `apply_part_graph`, then polls `get_execution_status`, and reports measured size and volume.
- [ ] **Step 3: The owner opens the file** in SOLIDWORKS and confirms it is right.
- [ ] **Step 4: The owner asks for a different part inside the rules** (for example, a 60 × 40 × 5 mm plate with one Ø20 mm hole). Expected: it builds the same way, showing nothing is hard-coded.
- [ ] **Step 5: Ask Claude for something outside the rules** (a fillet). Expected: a clear refusal through `list_feature_types` or validation, with no partial file.
- [ ] **Step 6: Record the owner's sign-off** and the results in `HANDOFF.md`, and mark the MVP done in section 18's current focus.
- [ ] **Step 7: Commit:** `docs: record part chain MVP sign-off`.
