# Specification Changelog

Changes to the [specification](README.md), newest first.

## What changed in 1.44

Adds circular pattern solid feature (`PAT-CIR-001` through `PAT-CIR-005`) to the Part Feature Graph IR and execution pipeline. Decided in [ADR-075](../adr/ADR-075-circular-pattern-feature.md).

- **IR and Schemas (5.7.3, 22.5.2):** creates `schemas/part-feature-graph/features/circular_pattern.json`, adds `circular_pattern` to `schemas/part-feature-graph/v0.json` node union, and updates `schemas/ipc/ops/feature.create.json` with `circular_pattern` type, `axis`, `count`, `spacing`, `equal_spacing`, and `reverse` parameters.
- **Compiler and lowering:** validates `circular_pattern` node constraints (seeds exist and reference cut features, count >= 2, spacing in (0, 360] degrees); lowers `circular_pattern` to `feature.create` operation.
- **Verification:** computes closed-form volume deduction ($N \times V_{\text{seed}}$) and rotated cylinder replication ($N \times \text{seed cylinders}$) for circular patterns in `cad-verification`.
- **Execution & Adapter:** handles `circular_pattern` in C# `FeatureAdapter.cs` via `FeatureManager.CreateDefinition(swFmCirPattern)` and `ICircularPatternFeatureData` with Mark 4 seeds, Mark 1 coaxial axis entity selection, and COM cleanup (`Marshal.ReleaseComObject`).
- **Authoring & Benchmark:** documents `circular_pattern` in authoring guide rules and examples, and adds circular patterned flange case to benchmark.
- **Checklists & Live:** adds live SOLIDWORKS integration tests promoting `PAT-CIR-001` - `PAT-CIR-005` to Verified.

## What changed in 1.43

Adds linear pattern solid feature (`PAT-LIN-001` through `PAT-LIN-004`) to the Part Feature Graph IR and execution pipeline. Decided in [ADR-074](../adr/ADR-074-linear-pattern-feature.md).

- **IR and Schemas (5.7.3, 22.5.2):** creates `schemas/part-feature-graph/features/linear_pattern.json`, adds `linear_pattern` to `schemas/part-feature-graph/v0.json` node union, and updates `schemas/ipc/ops/feature.create.json` with `linear_pattern` type and direction parameters.
- **Compiler and lowering:** validates `linear_pattern` node constraints (seeds exist and reference cut features, count >= 2, spacing >= 0.01 mm); lowers `linear_pattern` to `feature.create` operation.
- **Verification:** computes closed-form volume deduction ($N \times V_{\text{seed}}$) and cylinder replication ($N \times \text{seed cylinders}$) for linear patterns in `cad-verification`.
- **Execution & Adapter:** handles `linear_pattern` in C# `FeatureAdapter.cs` via `FeatureManager.CreateDefinition(swFmLPattern)` and `ILinearPatternFeatureData` with COM cleanup (`Marshal.ReleaseComObject`).
- **Authoring & Benchmark:** documents `linear_pattern` in authoring guide rules and examples, and adds linear patterned holes case to benchmark.
- **Checklists & Live:** adds live SOLIDWORKS integration tests promoting `PAT-LIN-001` - `PAT-LIN-004` to Verified.

## What changed in 1.42

Adds sketch straight slot primitive (`SK-ENT-021` Straight Slot) to the Part Feature Graph IR and execution pipeline. Decided in [ADR-073](../adr/ADR-073-sketch-straight-slot-primitive.md).

- **IR and Schemas (5.7.4, 22.4.1):** adds `StraightSlot` (`type: "straight_slot"`, `start_point`, `end_point`, `width`) to `schemas/part-feature-graph/v0.json` and updates `schemas/ipc/ops/sketch.create.json`.
- **Compiler and lowering:** validates straight slot dimensions (length >= 0.01 mm, width >= 0.01 mm); validates straight slot profiles as closed loops; lowers straight slots deterministically into two tangent lines and two semicircular CCW arcs for `sketch.create`.
- **Verification:** computes exact closed-form cross-sectional area, perimeter, center of mass, and bounding boxes for slot profiles in `cad-verification`.
- **Execution & Adapter:** handles `straight_slot` in C# `SketchAdapter.cs` with COM cleanup (`Marshal.ReleaseComObject`).
- **Authoring & Benchmark:** documents `straight_slot` in authoring guide and adapts `plate_slot` benchmark fixture to use the native primitive.
- **Checklists & Live:** adds live SOLIDWORKS integration tests promoting `SK-ENT-021` (Straight Slot) to Verified.

## What changed in 1.41

Adds sketch rectangle primitives (`SK-ENT-005` Corner Rectangle, `SK-ENT-006` Center Rectangle) to the Part Feature Graph IR and execution pipeline, and promotes sketch arc primitives (`SK-ENT-013`, `SK-ENT-016`) to Verified status on live SOLIDWORKS 2025. Decided in [ADR-072](../adr/ADR-072-sketch-rectangle-primitives.md).

- **IR and Schemas (5.7.4, 22.4.1):** adds `CornerRectangle` (`type: "corner_rectangle"`, `corner1`, `corner2`) and `CenterRectangle` (`type: "center_rectangle"`, `center`, `width`, `height`) to `schemas/part-feature-graph/v0.json` and updates `schemas/ipc/ops/sketch.create.json`.
- **Compiler and lowering:** validates rectangle bounds (minimum 0.01 mm, distinct diagonal corners); validates rectangle profiles as closed loops; lowers rectangles to canonical CCW connected lines for `sketch.create`.
- **Verification:** computes exact 3D bounding box, volume, and planar faces for rectangular profiles in `cad-verification`.
- **Authoring:** exposes `corner_rectangle` and `center_rectangle` in authoring guide and eval benchmark.
- **Checklists & Live:** adds live SOLIDWORKS integration tests promoting `SK-ENT-013` and `SK-ENT-016` (Arcs) plus `SK-ENT-005` and `SK-ENT-006` (Rectangles) to Verified.

## What changed in 1.40

Adds sketch arc primitives (`SK-ENT-013`, `SK-ENT-016`) defined by center, start, end, and direction (`ccw`/`cw`), supporting closed loops mixing lines and arcs for extrusions and cuts. Decided in [ADR-071](../adr/ADR-071-sketch-arc-primitives.md).

- **IR and Schemas (5.7.4, 22.4.1):** adds `Arc` entity (`type: "arc"`, `center`, `start`, `end`, `direction`) to `schemas/part-feature-graph/v0.json` and updates `schemas/ipc/ops/sketch.create.json`.
- **Compiler and lowering:** validates arc radius consistency within $10^{-6}$ mm, minimum radius $\ge 0.01$ mm, distinct endpoints; allows profiles composed of closed loops of lines and arcs; lowers arcs to `sketch.create` entity payload.
- **Verification:** computes exact 3D bounding boxes spanning arc extrema, cross-sectional area with circular segments for exact expected volume, and cylinder face expectations for extruded arcs.
- **Add-in:** `SketchAdapter.cs` maps `arc` to `ISketchManager.CreateArc` with COM cleanup.
- **Benchmark:** adds `plate_slot` to authoring evaluation benchmark cases.

## What changed in 1.39

Documentation only: no contract, schema or behaviour changes. Implementation status now has one home.

- **Implementation status (22.12):** capability status moves to the [implementation checklists](../implementation/README.md). 22.12 keeps only what they do not track (`in` units, `origin: read`, generated models), which also removes its outdated statement that `cad_references` is empty.
- **Register:** adds K30 (extrude and cut roles beyond the cap faces) and K31 (node fields with no effect).

## What changed in 1.38

Closes open decision K29 by measuring and verifying cap-face sketch frames (`<extrude_id>.start_face` and `<extrude_id>.end_face`) across all three standard datum planes (`plane:front`, `plane:top`, `plane:right`) in SOLIDWORKS 2025, hardens 3D part COM interop cleanup and verification contract type checks, and establishes the 13-prompt evaluation baseline.

- **Cap-face frames across all datum planes (5.7.4, ADR-070, K29 closed):** on `end_face`, the sketch axes equal the base plane's axes with the origin shifted by `depth` along the base normal. On `start_face`, the normal is reversed; on vertical cap faces (`plane:front` and `plane:right`) SOLIDWORKS keeps `+Y` as the sketch `+y` axis and mirrors `+x`, while on horizontal cap faces (`plane:top`) SOLIDWORKS keeps `+X` as the sketch `+x` axis and mirrors `+y` (`x = (1, 0, 0)`, `y = (0, 0, 1)`, `normal = (0, -1, 0)`).
- **Pure core packages (`cad-ir`, `cad-geometry`, `cad-references`, `cad-compiler`, `cad-verification`):** `FaceFrame.to_model` projects 2D cap-face coordinates into 3D model space across all 6 datum-and-cap combinations; `cad_geometry.signatures` exports `cap_face_frame` and `project_cap_face_point`; `cad_references.semantic` exports `resolve_cap_face_signature`; `expected_geometry` projects off-center cap-face cuts and cylinders on `plane:top` and `plane:right`.
- **Verification contract hygiene & COM lifetime (`cad-verification`, `ExecutionServer.Adapters`):** `evaluate()` rejects boolean/non-integer `error_code` and `entity_count` and non-boolean `is_warning`/`suppressed` as `not_evaluated` (`malformed_data`); C# 3D part adapters track all temporary `IFeature` and `IMassProperty` COM proxies in `ComScope`, close untitled documents if `SaveAs4` fails, and translate `COMException` on feature creation/rebuild into `BACKEND_REBUILD_ERROR`.
- **Evaluation set & live suite:** adds `blind_hole_start_face` (13 cases total: 10 build, 3 refuse), `tests/cad-benchmark/part_ir_baseline_answers.json`, and live SOLIDWORKS 2025 tests for `start_face`, `plane:top`/`plane:right` cap faces, and `block_centre_hole`.

## What changed in 1.37

A sketch may sit on an extrude's cap face, so "a hole, 4 mm deep, in the top face" can be built. Decided in [ADR-070](../adr/ADR-070-sketch-on-extrude-cap-face.md); measured by the [face spike](../superpowers/review/2026-11-06-face-sketch-spike.md); planned in [the face reference plan](../superpowers/plans/2026-11-06-face-reference-sketches.md).

- **IR (5.7.4):** a sketch `plane` may be `<extrude_id>.end_face` or `<extrude_id>.start_face`. No other faces, edges or offset planes. The sketch lists the extrude in its `dependencies`. The schema pattern already accepted `name.name`; the compiler now accepts these two roles.
- **Frames (measured on `plane:front`):** an end face has the base plane's axes with the origin moved by the depth; a start face has x mirrored and the normal reversed. A blind cut from a face goes into the body with `Flip=false`, `Dir=false`; from an origin plane it still needs `Dir=true`.
- **No persisted references:** the compiler states the face's outward normal and offset, and the add-in finds the extrude's planar face with that signature, selects it with `IEntity.Select4` and checks the opened sketch's axes (`REF_NOT_FOUND`, `REF_AMBIGUOUS`, `REF_SIGNATURE_MISMATCH`). K28 stays open for edges and later phases.
- **Contracts:** `sketch.create` takes `plane` or `face`; `feature.create` takes `host` (`face` for a cut whose sketch is on a face). The stage version of feature lowering is 0.3.0, so plan hashes change for graphs that use a face, and the golden plan's provenance changed.
- **Verification:** expected geometry places a cut from a face between `depth - h` and `depth` (end face) or `0` and `h` (start face), with x mirrored on the start face.
- **Authoring guide and evaluation set:** the guide teaches the face syntax and its frame; `blind_hole_top_face` is now a build case and `refuse_hole_in_side_face` replaces the old refusal.
- **Register:** adds K29 (the frame rule is unmeasured on `plane:top` and `plane:right`; the add-in fails safely).

## What changed in 1.36

Adds `get_authoring_guide`, the tool an agent reads before it turns a user's request into a Part Feature Graph, and states the refusal rule. No IR schema or add-in code changed, and no live SOLIDWORKS run was made.

- **New tool, `get_authoring_guide` (12.4.4, 12.4.5, 12.2):** core toolset, `store` kind, read-only, no input. It returns one Markdown guide: the workflow (decide, write, `validate_part_graph` until valid, state what will be built, `apply_part_graph`), the planes with their axes and normals, the validator rules, the limits, and validated worked examples. It is generated from the plane definitions and the supported feature list, so it cannot drift from them.
- **Refusal rule (owner decision, 2026-11-06):** when a request needs something the MVP cannot express (fillets, arcs, patterns, sketches on a face, more than one base extrude, assemblies, and similar), the agent replies that it cannot fulfil the request and never builds an approximation.
- **A tool, not an MCP resource:** the MCP front-end may import no `cad_*` package and reaches the core only through tools, so a resource would need a new core protocol path. ADR-044's "no prompts" is kept; the server states the workflow in its `instructions` instead.
- **Validator messages:** five rule messages now say what to change (second extrude, cut without the extrude dependency, open loop, hole or cut on or outside the edge), so an agent can repair a graph in one step.
- **Evaluation set:** 11 prompts (8 to build, 3 to refuse) with facts computed by plain arithmetic, a checker and a script (`scripts/score_part_ir.py`). It scores answers an agent produced; the tests call no LLM.
- **Plan:** [agent IR authoring](../superpowers/plans/2026-11-06-agent-ir-authoring.md).

## What changed in 1.35

Adds a coherent architecture reference for the IR, the compiler and the adapter, and aligns the topic files with each other. No schema or production code changed, and no live SOLIDWORKS run was made.

- **New sections, Proposed:** [§22 CAD IR](ir-specification.md) and [§23 Compiler Architecture](compiler-architecture-specification.md). They point to the topic sections for what is decided, and label everything new. 23.13 names one owner for each shared contract.
- **§8.9 extended, no new adapter file:** 8.9.11 maps the IR to native calls, with evidence levels; 8.9.12 is the add-in's half of reference resolution; 8.9.13 lists the raw facts it exposes; 8.9.14 maps concerns to their existing sections. 8.9.5 gains rows for selection failure, over-defined sketches, references and a blocked UI. A new mark, ◐, means read from the installed interop and help but never run.
- **API findings:** the 2025 help marks these obsolete: `InsertProtrusionSwept4`, `InsertCutSwept5`, `FeatureFillet3` for constant radius, `FeatureLinearPattern5` and `FeatureCircularPattern5`. It also documents that face IDs are removed on rebuild and tracking IDs last only until one.
- **Proposed ADRs:** [ADR-065](../adr/ADR-065-part-parameters-and-expressions.md) to [ADR-069](../adr/ADR-069-stable-operation-ids.md). None is applied.
- **Register:** adds K23 to K28.
- **Alignment fixes (wording only; each matched an accepted decision or the schema):**
  - 8.6.2 follows ADR-059: hidden control with no fallback, re-post, and the pipe thread's full list of answers. 8.6.1's example uses protocol `0.1`.
  - 8.3 rule 9: one conversion place per direction, as 8.7 and 8.8.9 already said.
  - 8.4 and 8.5, and 6.5.2's Undo row: part jobs use the working-file rule, not undo.
  - 6.3: preconditions are not plan content, because the schema has no such field.
  - 5.7.2 and 5.7.5: reference examples that the grammar rejects now say so (K23). 5.7.1 notes the ordering risk. 5.7.3 separates mirror from `pattern`, as Proposed, and states `spacing`'s two kinds.
  - 13.1: the `apply_part_graph` exception. 13.2.1: `evidence.json`, and `feature_ids` and `measured` from A3.
  - 4.6: parameters use `kind`, since 3.4.3 fixes units per document.
  - 5.6 cross-refers K25. 3.2, 6.3, 7.5, 9.3 and 10.2 cross-refer the new sections. 17: the adapters do not verify, and `execution-evidence/` is listed.
  - 18: the MVP is approved, as HANDOFF already said.

## What changed in 1.34

Delivers roadmap phase [A0](../plans/solidworks-adapter-roadmap.md): the contracts that ADR-063 and ADR-064 need now exist as schemas. The add-in and the job do not use them yet, so no job behaves differently.

- **Error catalogue:** adds `BACKEND_OPERATION_FAILED` (8.9.5) and `FEATURE_VERIFICATION_FAILED` (ADR-064), replacing their placeholders. ADR-037 lists both.
- **New schemas:** `schemas/execution-evidence/v0.json` (8.9.6), including `VerificationContract`, check results, `failure_class` and `blocked_by`; `schemas/ipc/ops/document.rebuild.json`.
- **`schemas/ipc/v0.json`:** adds `Observation` (8.9.3 rule 7) and `OperationFailureDetails` with `effect`, `stage` and `native` (8.9.5). `native` fields are absent when unknown, not null.
- **Operations:** `sketch.create` and `feature.create` results gain an optional `observation`, and `feature.create`'s `status` is limited to the four values of 8.9.3 rule 6. **Breaking for a plan:** `dir` leaves `feature.create` and the compiler (6.5.2), and the `feature_lowering` stage goes to 0.2.0, so every plan hash changes.
- **Journal:** the store schema gains `op_verified` (13.2.3). The journal reader follows in MVP Task 9a.
- **`cad-verification`:** `CheckResult.status` gains `warning` and `not_applicable`, and rejects a reason that does not fit its status (8.9.6). Nothing produces the new values yet.
- **8.9.3:** `document.rebuild` returns `rebuilt`, the call's own return, apart from the observed `ok` and `errors`, because a rebuild returning true does not mean error-free.
- **8.9.6:** the example gains `contracts` and `observation`, and `native_id` is an integer, as in the operation result. A contract check becomes `not_applicable` through `not_applicable_reason`, set from the IR alone.

## What changed in 1.33

Settles a contradiction between 6.5.3 and 6.7.4, finding V14 of the [verifiable compilation gap analysis](../superpowers/review/2026-11-05-verifiable-compilation-gap-analysis.md). No production code or schema changed: the code already behaved this way.

- **6.7.4 (owner decision, 2026-11-05):** a plan's `bundle` records each document's pinned revision, so two revisions of identical content give the same `operations` but different plan hashes. 6.7.4 used to say they gave an identical plan.

## What changed in 1.32

Adopts per-operation verification from the [verifiable compilation gap analysis](../superpowers/review/2026-11-05-verifiable-compilation-gap-analysis.md). No schema or production code changed, and the code does not follow this yet (roadmap A0, A2 and MVP Tasks 8 to 9b). No live SOLIDWORKS run was made.

- **New ADR:** [ADR-064](../adr/ADR-064-per-operation-verification-contracts.md), Accepted by the owner on 2026-11-05. It extends ADR-063.
- **New section:** [10.2.2 Per-operation verification](../architecture/verification-engine.md): contracts derived from the IR, a judgement before each next operation, fail fast, and cost tiers.
- **Changed:** 6.5.2 (a blind cut's direction leaves the plan and the wire), 6.5.3 (postconditions are names only), 8.4.1, 8.7 (`rebuild` is observed state), 8.8.9, 8.9.3 (`observation`), 8.9.5, 8.9.6 (`warning`, `not_applicable`, reasons, `failure_class`, `blocked_by`), 8.9.10, 10.2.1 and 13.2.3 (`op_verified`).
- **Open Decisions** ([register](open-decisions.md)): logged **K18** (cost of per-feature observation), **K19** (rebuild state on a document that was not rebuilt), **K20** (which mass property call to use) and **K21** (native type names for extrudes and cuts). **K22** is closed by owner decision: a feature warning blocks a commit in the MVP. **K15** is narrowed by the official API help: `AccessSelections` is ruled out for observers. 15 open decisions now.

## What changed in 1.31

Adds the compiler-oriented SOLIDWORKS adapter design, accepted by the owner on 2026-11-05. No production code or schema changed. No live SOLIDWORKS run was made for this design, and API facts not measured by the 2026-11-05 spike are marked unverified.

- **New sections:** [8.8 SOLIDWORKS Adapter Architecture](../architecture/solidworks-adapter.md) and [8.9 SOLIDWORKS Adapter Interface Specification](solidworks-adapter.md): layers, the five-stage handler, determinism levels R0 to R4, failure and retry rules, observation and verification, reconciliation limits, version isolation, operations by phase, error normalization with `details.effect`, an evidence record, `op:` variant capabilities and representative C# interfaces. 8.8.3 lists where the design departs from the request that prompted it, including that the compiler stays Python (ADR-001).
- **New ADRs:** ADR-058 to ADR-063, all Accepted.
- **New plan:** [SOLIDWORKS adapter roadmap](../plans/solidworks-adapter-roadmap.md), which builds on the part chain MVP plan and does not replace it.
- **Open Decisions** ([register](open-decisions.md)): logged **K13** (interop binding on a newer major), **K14** (native feature identity beyond reopen), **K15** (reading feature definitions without side effects), and **K16** (expected geometry beyond exact calculation); 11 open decisions now. K17 was logged and closed in this version.
- **Accepted, not applied yet:** `PROPOSED_OPERATION_FAILED` and the evidence schema (roadmap A0).
- **Owner decisions, 2026-11-05:** the compiler stays Python (ADR-001). ADR-059's COM release rule is adopted and applied to G1 and AGENTS.md section 2; the code does not follow it yet. The dispatcher and capability work joins the MVP as plan Task 7c. **Ledger (8.7, 13.2.3; closes K17):** an operation that may have changed the document and then failed is recorded and can never run again, `session.completed_operations` gains an additive `failed_operations`, and `operation_ids` stays successes only. Not implemented yet (plan Task 7a).

## What changed in 1.30

Specifies the part chain MVP ([design](../superpowers/specs/2026-11-05-part-chain-mvp-design.md), [plan](../superpowers/plans/2026-11-05-part-chain-mvp.md)), using the answers recorded by the [live API spike](../superpowers/review/2026-11-05-part-chain-spike.md). No schema or code yet; those come with the MVP's later tasks. New rules are **[Builder's call]** except where marked as the owner's decision.

- **Part template** (13.3, 6.5.2, 8.4.1; owner decision): new key `part.template`, the full path of a `.prtdot`, user file only, default unset. `part.create` uses the caller's template, otherwise this key. Unset or missing fails with `CONFIG_INVALID` or `FILE_NOT_FOUND` naming the setting. SOLIDWORKS's own default-template preference (`~BLANK_PART_TEMPLATE.prtdot` on the owner's install, which is not a file) is never used, and there is no fallback to an installed template.
- **Sketch axes and directions** (5.7.4): the table of axes, normals and blind extrude and cut directions for the three standard planes. A blind `cut_extrude` passes `Dir=true`; `Flip` does not work. Standard planes are found by `RefPlane` order and their normal is checked. `IMassProperty` uses `UseSystemUnits = true`. The `GetPersistReference3` fallback of 5.3.6 is not needed (A2 held).
- **Part operations** (6.5.2, 6.5.3): `part.create`, `sketch.create` and `feature.create` for the MVP, standard planes as role references (an exception to 6.5.1), documents addressed by full path only, existing paths refused because silent `SaveAs4` overwrites. A plan holds symbols (`$working`, node IDs) that the job binds at send time, one operation per batch. Selection uses `IFeature.Select2` and `Select4`; `SelectByID2` stays banned (8.3 rule 11).
- **Plan key** (6.7.4, 13.2.1): one key, the plan's content hash; an existing plan is reused and the reuse journalled.
- **`plan` job** (8.4.1, 8.7, 13.2.3, 13.2.1): lifecycle, publishing by no-replace rename, cancel boundaries, working files, `part.measure`, journal records `publish_intent` and `published` and the `document` action `create`, the `published_unconfirmed` warning, the `parts/` record and `part_result`.
- **Rule 13 and events** (8.3 rule 13, ADR-050; owner decision D1): the "AI job running" banner is not built for the MVP; `cancel_execution` stops a job; event detection is built. The add-in uses `RegenNotify`/`RegenPostNotify`, `FileSavePostNotify` and `DestroyNotify2`, not `FileSaveNotify` or `FileCloseNotify`, and checks a document with `GetOpenDocumentByName(fullPath)` before trusting an ownership entry. Part operations need no active document.
- **ADRs** (owner decisions for the MVP): ADR-032 gains the ownership table and close-tracking exceptions to "stateless"; ADR-046 gains the working-file rule instead of undo for part jobs and add-in ownership enforcement; ADR-050 records the D1 exception; ADR-037 adds `PART_VERIFICATION_FAILED` and the `PART_` prefix.
- **Verification** (10.2.1): the MVP checks and tolerances (±0.01 mm, ±0.01%), with the plate measured in the spike.
- **Revisions** (3.4.5, 12.4.2): `apply_part_graph` takes an optional `expected_revision`; identical content reuses a revision, different content without a match is `REV_CONFLICT`.
- **Tools and toolsets** (12.3, 12.4.4, 12.4.5, 12.5, 13.3): `mcp.toolsets` defaults to `["core"]` while drawings are frozen, and a disabled tool is refused over the core pipe. Four tools (`apply_part_graph`, `validate_part_graph`, `list_feature_types`, `get_feature_schema`) ship before Phase 1c under ADR-057. 12.5 allows new parts the system produced, never overwriting.
- **Open Decisions** ([register](open-decisions.md)): logged **K11** (events for an engineer's UI actions are not yet observed) and **K12** (measurement on curved bodies); 7 open decisions now (K3, J11, K8, K9, K10, K11, K12).

## What changed in 1.29

Adds the part chain MVP to the current focus of the roadmap (section 18): its stages, finish line and exclusions, linking its [design](../superpowers/specs/2026-11-05-part-chain-mvp-design.md) and [plan](../superpowers/plans/2026-11-05-part-chain-mvp.md), both awaiting the owner's approval. No contract changes; those come with the MVP's first specification task.

## What changed in 1.28

Rewrites the roadmap (section 18) for readability, adds the order of work for Phase 1, and records the owner's decision to freeze drawing work and build the part chain first. Phase scope, acceptance criteria and assumptions A1–A17 are unchanged.

- **Current focus** (section 18, [ADR-057](../adr/ADR-057-freeze-drawings-build-part-chain-first.md), owner decision): drawing work is frozen at commit `eea9389`, and development moves to the Part Feature Graph IR and an end-to-end MVP that produces a verified `.SLDPRT`. The Phase 1 work order is paused, except for M0 and the parts of M2 and M3 the part chain needs.
- **Phase 1 work order** (section 18) **[Builder's call]**: milestones M0–M11 from the [2026-11-05 architecture roadmap](../superpowers/review/2026-11-05-architecture-roadmap.md), with dependencies, completion criteria and how they feed phase acceptance. Owner decisions O1, O5 and O6 stay open, and ADR-056 stays Proposed.
- **Roadmap layout** (section 18): adds a phases-at-a-glance table, a goal for each phase, and grouped work items and acceptance lists.
- **Assumption register** (section 18): states that `docs/specifications/assumptions.md` does not exist yet and that M0 creates it.
- **Open Decisions** ([register](open-decisions.md)): logged items **K8** (snapshot keys when native names change or repeat), **K9** (view and annotation identity across sessions) and **K10** (form of the `produce_drawing` orchestrator); 5 open decisions now (K3, J11, K8, K9, K10).

## What changed in 1.27

Adds the Drawing Intent IR schema (§11.10), Resolved Dimension Scheme schema (§11.10.1), and backend annotation and dimension placement operation schemas (§6.5.2) for Phase 1c Annotation & Dimension Placement Pipeline.

- **Drawing Intent IR** (§11.10): authored JSON Schema in `schemas/drawing-intent/v0.json` specifying general tolerance, surface finish, datums, critical dimensions, GD&T callouts, and authored scheme overrides.
- **Resolved Dimension Scheme** (§11.10.1): authored JSON Schema in `schemas/resolved-scheme/v0.json` defining the full set of derived and authored dimensions shown, hidden, or omitted on drawing views.
- **Backend Annotation Operations** (§6.5.2): added schemas for `model_items.insert`, `dimensions.auto_arrange`, `center_mark.add`, `dimension.hide`, `dimension.show`, and `dimension.move` in `schemas/ipc/ops/`.
- **Contract Code Generation**: regenerated Python models (`cad_ir.generated.ipc`, `schemas.py`) and C# contract classes (`Messages.g.cs`).

## What changed in 1.26

Adds the Drawing Layout IR schema (§11.11) and backend drawing view operation schemas (§6.5.2) for Phase 1b Drawing View Pipeline.

- **Drawing Layout IR** (§11.11): authored JSON Schema in `schemas/drawing-layout/v0.json` specifying sheets, views, orientations, positions, ISO scales, view displays, annotations, tables, and title-block field overrides.
- **Backend Operations** (§6.5.2): added schemas for `view.create` and `view.update` in `schemas/ipc/ops/` with shared `ViewOutline` in `schemas/ipc/v0.json`.
- **Contract Code Generation**: updated Python models (`cad_ir.generated.ipc`, `schemas.py`) and C# contract classes (`Messages.g.cs`).

## What changed in 1.25

Closes Open Decision K7 with operation schemas for backend sheet format generation and drawing creation.

- **Backend Operations** (§6.5.2): added schemas for `sheet_format.generate`, `drawing.create`, and `document.save` in `schemas/ipc/ops/`.
- **Open Decisions** ([register](open-decisions.md)): closed item **K7** (backend sheet format generation path from Drawing Template IR); 2 open decisions remain (K3, J11).

## What changed in 1.24

Adds the Drawing Template IR module (§11.12, ADR-055), enabling CAD-neutral vector specification of sheet formats, borders, title blocks, and attribute link sources.

- **Drawing Template IR** (new §11.12): authored IR module defining paper size (A4-A0), orientation, border margins, title block zones and lines, static text, attribute link sources, and revision table placement.
- **New ADR-055**: sheet formats may be generated from Drawing Template IR alongside owner-supplied binary `.slddrt` files, extending ADR-050.
- **Shared IR Core** (§3.4.1, §3.4.2, §3.4.5): added `drawing_template` to `ModuleKey`, `DocumentRef`, and `ItemRef` in `schemas/common/v0.json` and `cad_ir.core.ids`. Late-bound `source` candidates exempted from bundle cross-module resolution. Multiple `drawing_template` documents allowed in an IR bundle.
- **Drawing Layout IR** (§11.11): a sheet specifies mutually exclusive `template` (`DocumentRef`) or `sheet_format` (path to `.slddrt`). Template-backed sheets omit redundant `size` and `orientation`.
- **Production Drawings & D8** (§11.2, §11.5.3): title block allows generated formats; D8 derives required fields and revision table checks from the template IR for generated sheets.
- **Configuration** (§13.3.4): TOML mapping files apply only to hand-made formats; generated formats require no TOML file.
- **Backend Operations** (§6.5.2): added `sheet_format.generate` operation, needed by `later`.
- **Open Decisions** ([register](open-decisions.md)): logged item **K7** (backend sheet format generation path); updated note on K3.

## What changed in 1.23

Records the six long-term architectural principles in 1.3. Numbers 1–11 are unchanged, so existing references ("principle 9") still resolve.

- **New principles** (1.3): 12 IR-first architecture (the IR is the core, not a wrapper around the SOLIDWORKS API); 13 Recoverability (find the actual model state after a failure; never blindly replay).
- **Sharpened** (1.3): 1 CAD-neutral semantics, not only concepts; 3 determinism covers execution, not only compilation; 5 indexes are never identity; 6 verification covers geometry, dimensions, tolerances and drawings against the specification; 7 points to 8.4 and 8.5.
- **Overview** (3): points to the principles.
- **New ADR-054**: the principles are binding; departing from one needs an ADR.

Also in 1.23 (nothing was released between 1.22 and 1.23): gaps found while building milestone 5 ([register](open-decisions.md), J12–J20 closed, J21 open). All **[Builder's call]**.

- **Errors** (ADR-037, 12.5, 13.2.2): new code `STORE_UNAVAILABLE` (`after_fix`) for a store file that cannot be read or written; a file that exists but cannot be read is `FILE_NOT_FOUND` with `details.reason: unreadable`; an unexpected exception in a tool call is a protocol error, not an envelope; in a job it is FAILED with `EXEC_INTERRUPTED`.
- **Tool contracts** (12.4.2, 12.4.5): an unknown tool name raises to the transport (protocol error); `elapsed_ms` is absent while `started_at` is null.
- **Paths** (12.5): alternate data streams (a `:` after the drive) are refused; a `$` is refused only as an environment reference; a store folder that resolves outside the project's allowed root is refused.
- **Lifecycle** (8.4): which `document.event` the job caused (the add-in tags events with the command's `_meta`); when the drawing is not closed, and what a failed close does; `STORE_UNAVAILABLE` as a failure.
- **Store** (13.2): I/O error rule, strict JSON, `job_id` must match its folder; recovery when a store is first opened at any time, the journal-wins rule bounded by the 8.4 table, RECOVERY jobs, orphan job folders, unreadable known-stores list; snapshots validated before they are stored; when clean-up runs in Phase 1a.
- **Configuration** (13.3): a relative `drawing.standard_dir` resolves against the installation root given to the core service.
- **ADR-053:** the engine lock is held across small record writes (never a `Backend` call), and what that costs on a slow disk.
- **G3:** `store` joins the allowed log fields; emitters use `error_code` and `reason`.

## What changed in 1.22

Closes gaps found when planning `check_drawing` and `get_drawing_report` over the store and jobs ([register](open-decisions.md), J1–J10), and logs one for the live read-back (J11). All **[Builder's call]**.

- **Lifecycle** (8.4): transitions to ABORTED and FAILED from every non-final state; PLANNED is the queued state; `queued_position` defined; FAILED final in Phase 1; what each state means for `check_drawing`, its cancel boundaries, and job warnings outside the report.
- **Job engine** (new ADR-053): a synchronous engine run by one worker thread; long-polls wait through the `Clock` port. Cancel during EXECUTING needs the transport milestone's reader thread.
- **IPC** (8.7): an unknown sheet fails `drawing.snapshot` with `IR_REFERENCE_UNRESOLVED`; `check_drawing` opens the drawing read-only with `document.open` and closes it if it owns it.
- **Tool contracts** (12.4): contract-file format and meta-schema `schemas/mcp/contract/v0.json`; annotation defaults; the table check; `ids`; invalid arguments are `IR_SCHEMA_INVALID`, unknown tools a protocol error; `ToolResult` with a one-line summary; cursor format; full Phase 1a contracts (12.4.5), with no `drawing_intent` argument until Phase 1b and no `scheme` section in Phase 1a.
- **File access** (12.5): checks as a pure function over the `FileSystem` port, `details.reason` values, store-folder hash. New error code `FILE_NOT_FOUND` with the `FILE_` prefix (ADR-037).
- **Store** (13.1, 13.2): `check_drawing` creates a store-side drawing record; record contents and `schemas/store/v0.json`; report meta files; drawing matching; known-stores list; lock, atomic write, journal append and order rules; Phase 1a recovery; what retention counts as a reference; the exact `.gitignore`.
- **Configuration** (13.3): `drawing.standard_dir` is a user-file key; environment values parsed as TOML; error locations; layer merging in `cad-application`; loading title-block mappings, none shipped until K3 closes.
- **Report** (11.5.4): store IDs and job warnings stay out of the report file.
- **Guidelines** (G2, G3): ports `BackendProvider`, `FileSystem`, `EventLog`; `FakeStore` is `FileStore` over `MemoryFileSystem`; where correlation IDs are made; the log sink drops unknown fields.

## What changed in 1.21

Closes gaps found when planning the IPC side ([register](open-decisions.md), K4–K6).

- **IPC messages** (new 8.7) **[Builder's call]**: JSON-RPC error codes, handshake order (an unauthenticated client gets no reply), `drawing.snapshot` as one command across sheets, `ops.apply` groups and outcomes, a repeated ID stopping a batch, ledger lifetime, `job.cancel` ordering, base64 `response.chunk`, client timeout behaviour, transcript format.
- **Type generation** (new ADR-051, changes ADR-035) **[Builder's call]**: one project-owned generator for Python and C#, in place of `datamodel-code-generator`. IPC types live in `cad_ir.generated.ipc`, so `cad-application` can use them under G2 (17, G2).
- **C# JSON library** (new ADR-052) **[Builder's call]**: `Newtonsoft.Json`. Assumption A17 added (18).
- **Contract tests** (15.5): C# rejection covers what deserialization enforces; transcripts are hand-written until live runs record them.

## What changed in 1.20

Closes gaps found when planning the rest of the Phase 1a checks ([register](open-decisions.md), K2, N3, R1), and logs one that needs the owner's sheet format (K3).

- **D5, D8, D10 without a Drawing Intent** (new 11.5.3) **[Builder's call]**:
  - D5 has two parts. `duplicates` covers duplicate parameters and closed chains, which need no scheme. `auxiliary_marking` needs a Resolved Scheme, so D5 cannot be `pass` without one.
  - D8 runs against an injected title-block mapping; a sheet without one is `not_evaluated`.
  - D10's save/reopen part under `check_drawing`, which never saves: a drawing read back with no unsaved changes counts as `verified`; otherwise `not_checked`, which is `not_evaluated`.
- **Drawing report** (new 11.5.4) **[Builder's call]**: contents, verdict rule, reason codes, and a `calibration` field that can only say `unverified` until Phase 0 calibration on real drawings.
- **Snapshot additions** (11.5.1): `parameters` and `parenthesized` on annotations; `sheet_format`, `title_block_fields` and `revision_table` on sheets; root `rebuild`. All optional. Hidden annotations are not exported.
- **Configuration:** new key `drawing.check.parallel_deg` (13.3.3); `revision_table` in the title-block mapping (13.3.4).
- **Assumptions:** A15 and A16 added (18). `check_drawing` may rebuild in memory (8.4).

## What changed in 1.19

Closes a gap found when planning the Phase 1a checks: 11.5.1 lists what the Drawing Geometry Snapshot holds but not how it is encoded ([register](open-decisions.md), N2).

- **Snapshot encoding** (11.5.1) **[Builder's call]**:
  - keys: pipeline tags, otherwise a kind prefix plus a hash of the native name; sheet order by `index`;
  - points in sheet mm from the lower-left corner; arcs stored exactly and tessellated by the checks;
  - text boxes stored raw with their read-back method, the font-metric margin applied by the checks;
  - extension lines carry their attachment entity; model edges carry a kind; hatching is never exported.
  - the arc sweep rule, judged with the angle quantum; checks run on the quantized snapshot;
  - center-mark and centerline annotation line work counts as model edges.
- **D1 chain and baseline exemption** (11.5.2) made exact: it applies only where every contact point lies on the shared extension line, inside the overlap of the coincident extension lines.
- Arc chord error is `drawing.check.epsilon_mm` / 2 (was 0.02 mm).
- D7 distance and precedence defined; soft metrics exclude shared extension lines, leader-to-target contact and non-visible edges (11.5).

## What changed in 1.18

Records the Phase 0 owner decisions (new ADR-050, accepted 2026-11-04):

- The agent shares the engineer's SOLIDWORKS session (8.3 rule 13); a dedicated instance stays only as the A12 fallback.
- The general tolerance designation is `ISO 2768-m` with ISO 22081 (11.2, 11.10 `general_tolerance` and its example).
- QA balloons are note-based balloons created by the pipeline (11.2).
- Writing custom properties and changing `MarkedForDrawing` flags in parts are allowed, each only by an explicit per-call option (ADR-022, 11.1, 11.4).
- No PDM is used; the PDM rules stay for other installations.
- The owner approved the v1.17 decisions in 3.4.8.

## What changed in 1.17

Closes a gap found when starting the Phase 0 schema work: 3.4.4 says schemas mark number kinds and unordered arrays, but not how ([register](open-decisions.md), N1).

- **Schema files** (new 3.4.8) **[Builder's call]**:
  - every `$id` is under `https://sw-mcp.invalid/schemas/`, and schemas refer to each other by relative `$ref`;
  - shared-core types live in `schemas/common/v0.json`, the error catalogue in `schemas/common/errors.json`, the bundle manifest in `schemas/bundle/v1.json`;
  - major version 0 is unstable, and ADR-042 applies from major 1;
  - the annotations `x-quantity` (number kind), `x-unordered` (set arrays) and `x-retryable` (default `retryable` per error code);
  - patterns are anchored and matched against the whole string.
  - the meaning of `safe`, `after_fix` and `never`; timeouts, interruptions and a lost connection are never `safe`;
  - integers are written without a fraction and stay at or below 2^53 − 1; ID-keyed objects use `propertyNames`.
- Validation errors are ordered by pointer token by token, with array indices compared as numbers (3.4.7) **[Builder's call]**.
- `geo:` reference IDs follow the item-ID grammar (3.4.2) **[Builder's call]**.
- 3.4.3 notes that equality uses the quantum as a tolerance while hashing uses rounded values, so equivalence is decided by hash.

## What changed in 1.16

Closes a gap found in the implementation-readiness review: D1–D3 had no exact geometric meaning, so two implementations could disagree on the same drawing ([register](open-decisions.md), K1).

- **Geometric tests for D1–D3** (new 11.5.2) **[Builder's call]**:
  - the primitives the tests use: dimension lines (leaders included), extension lines, arrowheads, text boxes and model edges (centerlines and center marks included, hatching excluded);
  - an equality tolerance of 0.01 mm in sheet space, and touching counts as crossing;
  - the exceptions for D1: shared extension lines in chain and baseline dimensions, and an arrowhead touching its own extension line or the edge it points at;
  - clearances: 0.5 mm between text boxes, 0.25 mm from a text box to another annotation's lines and to model edges;
  - text boxes measured from font metrics are enlarged by 0.1 × text height on each side and marked as estimated;
  - the contents and order of each failure record, and a Phase 0 calibration on the owner-approved drawings.
- Configuration (13.3.3) gains the `drawing.check.*` keys for these thresholds.
- Repository layout (17) adds `schemas/mcp/` (tool contract files, 12.4.1) and `schemas/config/` (13.3.2), which other sections already required.

## What changed in 1.15

Closes the last open decision; the [register](open-decisions.md) now has no open items.

- **Compiler stage contract** (new 6.7, C4):
  - every stage is a pure function of its input and a recorded context;
  - the Geometry Resolver asks for missing geometry facts through `needs` instead of fetching them, and the driver gathers them in one `geometry.candidates` call, at most once per reference;
  - a table of each stage's input, output, context and diagnostic codes;
  - stopping rules: an error stops after its stage, all errors of a stage are reported, and the Semantic Validator reports every module;
  - byte-identical plans for the same bundle and context, a plan cache keyed by bundle and context hash, per-stage versions, and the 500 ms target.
- ADR-037 gains `IR_SCHEMA_VERSION_UNSUPPORTED`, `IR_RULE_VIOLATED`, `COMPILE_FAILED` and `COMPILE_PLAN_INVALID`.

## What changed in 1.14

Settles every open decision that blocked Phase 1b, plus C3 ([register](open-decisions.md)). Only C4, which blocks Phase 1c, remains open.

- **IR passing and patches** (new ADR-048, M2):
  - every collection of identified items is now a JSON object keyed by item ID, in all modules and derived artifacts (3.4.1);
  - documents are created by value once and changed by RFC 6902 JSON Patch with `expected_revision`, at most 200 operations;
  - every other tool takes references, and bundles list only stored documents.
- **Reference resolution** (new ADR-049, C3): the add-in gathers candidates in one `geometry.candidates` call; Python applies role rules and scoring and pins persistent IDs; the add-in dereferences and re-checks signatures at execution. This covers the Phase 1b stopgap at Drawing Intent intake and the Phase 1c compiler. ADR-036 gains the command, and ADR-037 gains `REF_SIGNATURE_MISMATCH` and `REF_NOT_IN_VIEW`.
- **Backend operations and Execution Plans** (new 6.5, C1):
  - an operation schema with idempotent operation IDs, one document per operation, and stop-on-first-failure;
  - the operation vocabulary by group and increment;
  - the Execution Plan with provenance, recorded defaults, sequenced operations, postconditions and verification points, cut into batches of at most 100 operations;
  - the drawing pipeline emits the same operations step by step.
- **Capability profile** (new 6.6, C2): backend versions, supported operations, API capabilities, licensed modules and feature coverage, hashed into every plan and report and checked before execution.
- **Validation errors** (new 3.4.7, I4): JSON Pointer per error, stage order, all errors per stage up to 50, deterministic order, warnings, patch errors.
- **Feature schema guide** (new 5.7, I5): node fields, naming, ParamRef paths, shared objects (`end_condition`, `thin`, `pattern`, `hole_spec`, `sheet_metal`), sketch entities, relations and dimensions, roles, and a defaults table versioned with the compiler. Sketch axes per standard plane are recorded in Phase 0.
- **Read path** (new 5.8, I6): one read-only graph per part and configuration; node IDs `f<GetID>`; dimensions `d<index>` with `driven_by`; recognized attributes, unrecognized features and equations; dirty parts not stored; `swdim:` conversion at intake. Assumption A2 also covers dimension enumeration order.
- **Examples converted to keyed collections:** Part Feature Graph (5.4, now matching 5.7), Design Intent requirements, Drawing Intent exceptions, critical dimensions and GD&T, Resolved Scheme entries, Drawing Layout sheets, views and annotations (with lower-case IDs), and Assembly components and mates.
- Cross-references updated in 6.3, 7.5, 12.4, 3.4.5, 15.5 and guideline G2.

## What changed in 1.13

Settles every remaining open decision that blocked Phase 1a ([register](open-decisions.md)).

- **Tool contracts** (new 12.4, M1):
  - one contract file per tool, from which tool definitions, handlers and tests are generated;
  - shared input and output conventions (references, `detail`, cursor pagination, `expected_revision`);
  - four tool kinds (`store`, `cad-read`, `cad-session`, `job`) with concurrency and time limits;
  - a table assigning all 50 tools a toolset, phase, kind and mutation flag;
  - the four Phase 1a contracts in outline.

  12.3 gains a `verification` toolset, and its `core` and `drawing` rows now point to the table.
- **File access** (new 12.5, M5): allowed roots from user configuration only, path checks, how a file's project is found, and stores kept outside PDM vaults.
- **Jobs over MCP** (new ADR-043, M3): polling with long-poll `wait_ms`, progress notifications optional, no MCP tasks in Phase 1, 7-day retention.
- **MCP baseline** (new ADR-044, M4): minimum protocol revision 2025-06-18; structured output plus a one-line text summary; resources for reports, snapshots, modules and schemas; no prompts, sampling, elicitation or roots.
- **SOLIDWORKS versions** (new ADR-045, S1): build against the oldest supported version, newer APIs behind named capabilities, versions admitted by passing the benchmark.
- **Add-in runtime** (new 8.6, S2–S4):
  - loading with or without the launcher;
  - a user-only session file as the only token handoff (replacing the launcher handoff in 8.2 and ADR-036);
  - the pipe thread and UI thread split;
  - time limits and heartbeat;
  - the settings guard that restores the engineer's preferences, including after a crash.

  New assumption **A14**: commands posted to the UI thread run reliably.
- **Document ownership and outputs** (new ADR-046, E2): owned vs borrowed documents, saving only on COMMITTED, `.failed` and `.partial` copies, and overwriting only drawings the store proves the system produced, with backups. 11.6 updated.
- **Project store and journal** (new 13.2, E1 and X2): store layout, a single writer with a lock, atomic writes, the journal record types, Phase 1 crash behavior, retention, and what goes into version control.
- **Configuration** (new 13.3, X3): sources and precedence, security keys from the user file only, validation, the key table, and the title-block mapping format.
- **Test data custody** (new ADR-047, T2): Git LFS for benchmark binaries; the holdout set only on the SOLIDWORKS CI machine.
- **Testing** (new 15.5 and 15.6, T1 and T3): contract tests for schemas, compatibility, MCP tools and both protocols from recorded transcripts; no retries, a quarantine rule, determinism tests, live-suite isolation, coverage on Python and C# `Core`.
- **Implementation guidelines** (new page; S5, X4, X5): G1 COM objects in the add-in, G2 Python layering and ports, G3 logging and correlation.
- Error catalogue (ADR-037) extended with the codes these sections use, including new `STORE_` and `CONFIG_` prefixes. ADR-036 gains `session.ping` and `session.completed_operations`.

## What changed in 1.12

Settles the first five items of the [open-decisions register](open-decisions.md).

- **Core service topology** (new ADR-041, X1): Python splits into a long-lived per-user **core service**, which owns tool handlers, jobs and their queue, the journal, the store and the add-in connection, and thin stateless stdio **MCP front-ends**, one per agent client. Jobs survive an agent disconnecting; several agents share one queue per SOLIDWORKS session. The front-end reaches the core over a second user-only pipe with ADR-036 framing. Updated 8.2, 8.4, 14, 17, ADR-034 and ADR-036.
- **Shared IR Core** (new section 3.4, I1–I3):
  - identifier grammars and module keys (`part`, `assembly`, `design_intent`, `drawing_intent`, `drawing_layout`);
  - one typed reference grammar: `DocumentRef`, `ItemRef`, `LocalRef`, `IntentItemRef`, `ParamRef`, `GeometryRef` (`feature.role`, `geo:`, `plane:`, `origin`, `datum:`) and the stopgap `swdim:`, plus the scoped references that resolve in a document the module names;
  - units (lengths `mm`/`in` per document, angles always degrees), numeric quanta, NFC text;
  - canonical form (RFC 8785) and `sha256:` content hashes; derived Resolved Scheme IDs `ds_<slug>_<hash6>`;
  - the document header, store-assigned integer revisions that are never rewritten, and the IR bundle manifest.
- **Compatibility policy** (new ADR-042, V1): one rule set for IR, derived artifacts, MCP tools, IPC, configuration and the store, covering what a minor version may change, reader behavior per contract, migration on read, deprecation and the CI contract diff.
- **Examples fixed to 3.4:**
  - Drawing Intent `design_intent_ref` becomes `design_intent` (a `DocumentRef`), and `documents` is added to the example;
  - `gdt` entries and surface-finish exceptions get `id`s;
  - the Resolved Scheme example uses computed IDs, `{ "critical": … }` tolerances and `plane:right` in place of the nonexistent `datum:B_plane`;
  - the Layout IR uses `intent` and prefixed `intent_ref` values;
  - Design Intent requirements use `targets` and lowercase IDs;
  - Assembly components refer to part documents only;
  - 11.1 writes stopgap references as `swdim:` and `geo:`.
- Register: X1, I1, I2, I3 and V1 moved to "Closed".

## What changed in 1.11

- **Verb-first tool names** (owner decision, new ADR-040, 12.1): every MCP tool is now `<action>_<object>` (`apply_part_graph`, `produce_drawing`, `check_drawing`, `get_execution_status`), replacing the noun-first rule from 1.8. The rule against sharing a name with the reference implementation stays; because `open_document`, `save_document` and `close_document` would collide, all six file tools use `cad_file` instead: `list_cad_files`, `create_cad_file`, `open_cad_file`, `save_cad_file`, `close_cad_file`, `inspect_cad_file`. All 50 tools in 12.2 and every mention across the spec are renamed, and job types (8.4) follow their tools (`produce_drawing`, `check_drawing`). Checked against the 51 tools the reference server exposes: no collisions.

## What changed in 1.10

Changes from a development-readiness review. The specification is now split across `docs/` by topic, with section numbers unchanged (map in [README.md](README.md)).

- **Toolchain decided** (new ADR-034 to ADR-039, all Proposed): CPython 3.13 with a uv workspace and the official MCP SDK; JSON Schema 2020-12 files in `schemas/` as the source of truth, with Python and C# types generated from them; an IPC protocol of length-prefixed JSON-RPC frames over a user-only named pipe with a versioned handshake; one error catalogue and MCP response envelope; SDK-style net48 add-in projects with a SOLIDWORKS-free `Core`; one monorepo with hosted and self-hosted CI.
- **Repository layout** (17) rewritten per ADR-039: the root is `sw-mcp`; C# lives only in `apps/execution-server/`, which now contains the SOLIDWORKS adapters; `application/` becomes the Python package `packages/cad-application/`.
- **Phase 0** (18) starts with repository and CI setup, and its schema work includes the IPC messages and error catalogue. New assumption **A13**: SOLIDWORKS loads a per-user registered add-in.
- Cross-references to the new ADRs in 8.2 (IPC) and 12.3 (response envelope).
- Fixed: 11.1 listed three geometry-reference forms but said "two"; the Drawing Layout IR sheet field is `scale`, matching its example (11.11); the assumption register's location is `docs/specifications/assumptions.md` (18).

## What changed in 1.9

Changes from an architecture review.

- **Phase 1 in three increments** (18, ADR-030): 1a checks existing drawings, 1b runs the pipeline on hand-modelled parts, 1c adds IR-built parts. Reference parity is no longer P0. The reference implementation runs alongside until parity at the end of Phase 2 (new 2.4).
- **Drawing Geometry Snapshot** (new 11.5.1, ADR-031): a versioned record of read-back lines, text boxes and edge polylines. Checks, offline tests and benchmark replay use it; the as-built Layout IR is derived from it.
- **Job model and ownership** (8.2, 8.4, ADR-032): one job lifecycle for plans, drawing production and checks. Python owns job state and the journal; the add-in is stateless apart from completed operation IDs. IPC commands are coarse; the pipe is user-only with a session token.
- **Bounded re-layout** (11.6, 16): at most 8 iterations per sheet, predicted geometry checked before each apply, and an end-to-end time target for `drawing_produce`.
- **Sharing SOLIDWORKS with the engineer** (8.3 rule 13): banner with Stop, user edits interrupt the job cleanly; a dedicated instance is an open owner decision.
- **Phase 1 face references** (11.1): feature-plus-role references and `geometry_inspect` reference IDs, so agents can name datum and GD&T faces without a pick.
- **Storage and document identity** (new 13.1, ADR-033): a plain-file project store; parts identified by PDM ID or path plus fingerprint, never by writing into them; lost state makes annotations pinned; updates take `expected_revision`.
- **Dimension scheme split** (11.10.1, ADR-023 revised, 3.3 rule 8): authored entries stay in the Drawing Intent IR (`scheme_overrides`); the pipeline-owned Resolved Scheme holds the derived result, with stable IDs, and never bumps the intent revision.
- **Assumption register** (18, Phase 0): each unproven API assumption with its test, fallback and the increment it blocks.
- **Holdout set** of the owner's real parts in the drawing benchmark (11.8).
- API verification is P0 (2.1, 10.2). Principle 1 states that the drawing cleanup steps are SOLIDWORKS-specific for now.

## What changed in 1.8

Changes from a second review focused on the SOLIDWORKS API and ISO drafting.

- **Functional reference dimensions.** A driven dimension that replaces a non-functional model dimension is shown without parentheses and carries its tolerance. Only true auxiliary dimensions keep parentheses (ISO 129-1). D5 checks this (11.4, 11.5).
- **Pins are detected relative to the view and attachment**, not by absolute sheet position, so model changes and view moves no longer pin annotations by accident. Phase 0 proves a durable annotation tag (11.11).
- **In-process execution.** The C# executor runs as a SOLIDWORKS add-in on SOLIDWORKS's own STA thread and talks to Python over local IPC. It gains document events for external-edit detection (8.2, 9.3, ADR-028).
- **`MarkedForDrawing` policy.** Model-item insertion depends on a part-level flag. The pipeline does not change it without permission (11.4).
- **Phase 1 is Read-first.** Tier 1 Read for all features. Create only for what IR-built benchmark parts need; the rest of Tier 1 Create moves to Phase 2 (2.1, 5.3.2, 18, ADR-029).
- SOLIDWORKS API rules added:
  - Feature identity by `IFeature.GetID()` (5.3.6).
  - Deterministic creation: `AddToDB`, no inference, selection by entity and mark, dialog suppression (8.3).
  - System-unit API variants only (8.3).
  - Undo objects as a cheap rollback (8.5).
  - Model-to-view entity mapping for drawing references (7.5).
- Equations, global variables and linked dimensions get Read support in Tier 1. Equation-driven dimensions are not driving parameters for D4 (5.3.2, 11.5).
- New view types: broken, broken-out section, removed section, aligned section, crop (11.6, 11.11).
- Read-back time gets its own target (16). Drawings open fully resolved, never in Detailing Mode (11.5). Service-pack test matrix (15.2). Macro execution is banned (14).
- **Tool names are distinct from the reference implementation's** (owner decision). All tools use noun-first `<object>_<action>` names (`document_open`, `part_graph_apply`, `drawing_produce`). Distinctive action words the reference uses are replaced (`apply` for `submit`, `check` for `verify`, `diff` for `compare`), and a CI check rejects any name shared with the reference (12.1).
- Fixed inconsistencies: one general tolerance default, the end-to-end flow follows task composition, leftover "Feature Graph IR" names, tool names in 12.2, and the meaning of medium confidence (7.4).

## What changed in 1.7

- **Task-driven IR composition** (section 3.3, ADR-026) replaces the single IR chain from 1.6. The system now consists of a shared IR core (IDs, references, units, types, validation) and independent domain modules:
  - Part Feature Graph IR
  - Assembly Graph IR (optional)
  - Design Intent IR (optional)
  - Drawing Intent IR (optional)
  - Drawing Layout IR (optional)

  A task uses only the modules it needs. A task-composition table and two worked examples (plastic housing, spring-driven injector) show which.
- Composition rules:
  - Tasks submit an IR bundle.
  - Each module declares the modules it depends on.
  - Modules refer to each other only through shared-core references.
  - Each value has one owner, with fallbacks when the owner is absent.
  - Changes reach only dependent modules.
  - Modules evolve independently.
- New section 5.6, *Assembly Graph IR*: components, hierarchy, mates, interfaces and motion. v0 (standard mates) is in Phase 2, mechanical mates and interfaces are P3, and motion studies are P4.
- Design Intent IR is optional:
  - Drawings no longer need it. Without it, process, material, treatment and metadata come from the part or from a new Drawing Intent `context` field, and inspection items use `inspect: true`.
  - The minimum version's schema is defined in Phase 0 and implemented in Phase 3 (P2), where requirement checks first use it.
- Feature Graph IR is renamed to Part Feature Graph IR, and section 5 now covers the Part Feature Graph and Assembly Graph IRs.

## What changed in 1.6

- The IRs now form one chain (section 3.3, ADR-003):
  **Design Intent IR** (functional / manufacturing / inspection requirements) → **Feature Graph IR** (CAD geometry and feature definition) → **Drawing Intent IR** (dimensions, GD&T, datums, surface finish) → **Drawing Layout IR** (views, annotations, positioning, layout) → **SOLIDWORKS execution backend** (parts, assemblies, drawings, PMI).
- The Design Intent IR is back at the top of the chain. A minimal Design Intent IR is now P0 (4.3), and the full constraint model stays P3.
- Fields have moved between IRs:
  - Process, material, treatment, manufacturing options, functional requirements, inspection requirements and part metadata moved from the Drawing Intent IR to the Design Intent IR.
  - The Drawing Intent IR keeps dimensions, tolerances (including the general tolerance), GD&T, datums and surface finish. Its items cite the requirement they serve.
- The Drawing Intent IR moved from 4.3 to 11.10, its dimension scheme to 11.10.1, and the Drawing Layout IR to 11.11.
- Functional features name what the requirements apply to. Feature Graph nodes declare which functional features they realize, so references always point up the chain.
- Hand-modelled parts get a read-only Feature Graph built from the feature tree, so the chain holds for every part.
- The backend can emit the Drawing Intent IR as 3D PMI (SOLIDWORKS MBD / DimXpert) as well as drawings (P2).

## What changed in 1.5

- Three IRs with strict boundaries (new section 3.3, ADR-003):
  - **Feature Graph IR** describes geometry and modeling features.
  - **Drawing Intent IR** describes what the drawing must communicate: dimensions, tolerances, datums, surface finishes and drawing requirements.
  - **Drawing Layout IR** describes how the drawing is arranged: sheets, views, annotation positions, text layout and pinned annotations.
- Drawing Intent is now an IR in its own right, no longer a "slice" of the Design Intent IR. The future full Design Intent IR shares its common types instead of absorbing it (4.2).
- Drawing Intent IR gains a `dimension_scheme`: the full resolved set of dimensions, notes and callouts. Cleanup and gap filling derive it, and engineers can override it. Hidden-dimension tracking moves there from the pipeline (4.3.1, ADR-023).
- New section 11.10 defines the Drawing Layout IR. It covers the planned vs as-built layouts, pinned-annotation detection by diffing them, and the schema and an example. Pinned annotations now live in the Layout IR instead of the drawing report.
- New drawing tools: `get_drawing_layout` and `update_drawing_layout` (12.2 G).

## What changed in 1.4

Changes from a review by a SOLIDWORKS user:

- D4 completeness now means that the shop can work out every size and position from the drawing, relative to the datums (functional dimensioning). Parameter coverage remains only as a quick proxy. A derived or reference dimension may cover a hidden model dimension (11.5, ADR-020).
- DimXpert is evaluated in Phase 0 as a source of dimensions alongside model items. It is also the path for imported bodies that have no feature tree (11.1, 11.4).
- Drawing Intent gains `configuration` and per-face `surface_finish`. GD&T and datums distinguish surfaces from features of size (4.3).
- Configurations get Read support in Tier 1 (5.3.2).
- Features and planes are identified independently of the SOLIDWORKS UI language and of user renames (5.3.6, ADR-021). The stopgap reference syntax is corrected (11.1).
- The pipeline never modifies the user's source part without permission. PDM and read-only files are handled explicitly (11.1, 14, ADR-022).
- D3 is narrowed to text over geometry. Dimension lines crossing edges become a soft metric. D9 adds center marks, centerlines and tangent-edge display.
- Added to the spec:
  - SOLIDWORKS API and runtime constraints: display-data read-back, high-quality views, a visible interactive session, a single unit-conversion boundary, and the limits of re-layout (8.3, 11.6).
  - Pinned annotations, so later re-layouts keep engineers' manual edits (11.6, 11.7).
  - Standards: ISO 5455 scales, the ISO 2768-2 → ISO 22081 transition, ISO 8015, the ISO 21920 support check, and the hole-callout format file (11.2).
  - Molded draft dimensioning convention, a decision on QA balloons (Inspection add-in vs notes), and a revision-table check (11.3, 11.5).

## What changed in 1.3

- The reference implementation is named only in this header. The system is an independent implementation, and no code is copied from the reference (ADR-010).
- The fine-grained toolset is renamed `detail`. The default toolset profile is now `core` + `drawing`.

## What changed in 1.2

- Feature taxonomy (5.3) is now tiered by benchmark need. Each feature type has **Create** or **Read** support. Generic dimension read covers unrecognized features. An explicit out-of-scope list is added.
- New section 12.3, *Tool Surface and Token Budget*. Features are IR data, not tools. Schemas are served on demand. Tools are grouped into toolsets. Responses are summary-first. Token budgets are enforced in CI.

## What changed from 1.0

- **Production-ready 2D drawings are now the first priority** (previously P2 / Phase 4). New section 11 defines them.
- Priority table and roadmap reordered: Drawings → Geometry References → Requirement Checks → Incremental Editing.
- Design Intent IR is split: a **minimal Drawing Intent slice** now (critical dimensions, tolerances, material, process, finish); the full IR and natural-language interface later.
- Added section 2.3 *Reference Baseline*: what the reference implementation already does, as the capability level to match.
- Assembly and drawing capabilities are carried over, not deferred.
- Added the overengineering risk and anti-goals.
