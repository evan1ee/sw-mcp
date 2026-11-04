# 18. Roadmap

> Specification v1.20, section 18. Index and section map: [specifications/README.md](../specifications/README.md).

## Phase 0 — Audit and Contracts

- Set up the repository and CI per ADR-034 to ADR-039: `git init`, uv workspace, C# solution, hosted CI, and the self-hosted runner on the SOLIDWORKS machine.
- Study the reference implementation against section 2.3. Record its behavior, tool contracts and known failures, including why its drawings cross dimensions. Its source is not in this repository. This is read-only study: no code is copied.
- Define the schemas (section 3.3) as JSON Schema files in `schemas/` (ADR-035):
  - the IPC messages (ADR-036) and the error catalogue (ADR-037)
  - the shared IR core and the IR bundle
  - additions to the Part Feature Graph (`realizes`, `origin`)
  - the Drawing Intent IR, including `scheme_overrides` and `context`, and the Resolved Scheme
  - the Drawing Layout IR
  - the drawing report
  - the Design Intent minimum and Assembly Graph v0 schemas, so their references stay stable before they are implemented
- Build the drawing benchmark parts and owner-approved reference drawings.
- Obtain the owner's company sheet format and title block; map its fields (and their source: part property, drawing property or intent).
- Evaluate DimXpert vs model-item insertion on the benchmark parts and on one imported body; record the outcome in ADR-012.
- Check API availability of Auto Arrange Dimensions, and SOLIDWORKS 2025 support for ISO 21920 surface texture symbols.
- Prove each SOLIDWORKS API assumption in the assumption register below with a small live test, and record the outcome there.
- Decide with the owner: the holdout parts they supply (11.8). Decided in [ADR-050](../adr/ADR-050-phase-0-owner-decisions.md): shared SOLIDWORKS session; `ISO 2768-m` with ISO 22081; note-based QA balloons; custom-property and `MarkedForDrawing` writes allowed by explicit per-call option; no PDM. The owner supplies the company sheet format.
- Write ADRs for decisions in section 19.
- Map the reference implementation's feature support onto the tiers in 5.3, and its tools onto the toolsets in 12.3. Record its full tool list for the name-clash CI check, and produce the mapping table from its tool names to this system's (12.1).
- Measure the reference implementation's token baseline (tool-definition size, responses on a few sample parts) as the bar to beat.

**Deliverables:** reference study notes, schemas, benchmark set, the completed assumption register.

### Assumption register [Builder's call]

The design rests on API behavior not yet proven. Each assumption has a live test, a fallback, and the increment that cannot start until it is settled. An assumption whose test fails switches to its fallback; the spec section it names is updated in the same change. The register lives in `docs/specifications/assumptions.md` once Phase 0 starts and is kept current.

| # | Assumption | Fallback if it fails | Spec impact | Needed by |
| --- | --- | --- | --- | --- |
| A1 | An in-process add-in with named-pipe IPC is stable, and read-back meets section 16 (ADR-028) | Read back only views changed since the last snapshot; if still too slow, revise the target in 16 with the owner | 8.2, 16 | 1a |
| A2 | `IFeature.GetID()` is stable across save/reopen, rename and rebuild | `GetPersistReference3` (5.3.6) | 5.3.6 | 1b |
| A3 | A durable annotation tag survives save/reopen and hide/re-insert (pipeline-set name or attribute) | Match by kind plus attachment entities; any annotation that cannot be matched uniquely is treated as pinned (13.1) | 11.11 | 1b |
| A4 | `IDisplayData` gives text-box extents for every annotation kind | Font metrics, marked in the report (11.5) | 11.5, 11.5.1 | 1a |
| A5 | It is known which `IDimension` value calls use document units | — (this only decides which calls the code check bans) | 8.3 rule 9 | 1a |
| A6 | Undo objects wrap a multi-feature plan and roll it back | Checkpoints with Save Copy only (8.5) | 8.4, 8.5 | 1c |
| A7 | Parentheses can be turned off on a toleranced reference dimension under the ISO standard file | Do not replace non-functional model dimensions; keep them shown and report them as a soft metric until the owner decides | 11.4, D5 | 1b |
| A8 | `MarkedForDrawing` leaves few enough gaps on hand-modelled parts that gap filling stays small | Ask the owner to allow the flag-change option (ADR-022) for the benchmark parts | 11.4 | 1b |
| A9 | SOLIDWORKS 2025 draws ISO 21920 surface texture symbols | ISO 1302-style symbols, gap recorded (11.2) | 11.2 | 1b |
| A10 | Auto Arrange Dimensions is usable through the API as a first placement pass | Placement engine does the first pass itself | 11.4 | 1b |
| A11 | DimXpert gives usable functional dimensions, including on imported bodies | Model items only; imported bodies reported unsupported (11.1) | 11.1, 11.4, ADR-012 | 1b |
| A12 | The agent can share the engineer's SOLIDWORKS session under 8.3 rule 13 | Dedicated second SOLIDWORKS instance, subject to the license check | 8.3 | 1a |
| A13 | SOLIDWORKS 2025 loads an add-in registered for the current user only (`HKCU`) (ADR-038) | Elevated machine-wide `RegAsm /codebase` registration script | 8.2 | 1a |
| A14 | Commands posted from the add-in's pipe thread through the UI thread's synchronization context run reliably, and are deferred, not lost, while SOLIDWORKS is busy or showing a modal dialog (8.6.2) | Drive the queue from a SOLIDWORKS idle-notification handler instead | 8.6.2 | 1a |
| A15 | The API gives what 11.5.1 needs for D5 and D10: a dimension's model parameter full name, its parentheses state, dangling state (`IAnnotation.IsDangling`), and whether an attachment is a silhouette edge | Field left out, so the check reports `not_evaluated` (11.5.3) until another source is found | 11.5.1, 11.5.3 | 1a |
| A16 | `check_drawing` can rebuild a borrowed drawing in memory and read its unsaved-changes state without leaving it changed for the engineer (ADR-046) | Read the last rebuild state without forcing a rebuild, and record that in the report | 8.4, 11.5.3 | 1a |

## Phase 1 — Production Drawings

Phase 1 ships in three increments, each usable on its own (ADR-030) **[Builder's call]**. The reference implementation keeps serving everything else meanwhile (2.4).

### Phase 1a — Drawing checks on existing drawings

- Execution server (add-in, IPC, job model, session rules: 8.2–8.4), launcher, structured logs.
- Drawing read-back into the Drawing Geometry Snapshot (11.5.1) and the as-built Layout IR (11.11).
- Hard checks D1–D3, D5 (duplicates only), D7, D8 and D10 on any drawing, including hand-made ones, through `check_drawing` and `get_drawing_report`. D4, D6, D9 and the auxiliary-marking part of D5 need a Drawing Intent IR and report "not evaluated" without one; a report with unevaluated checks is never "done".
- Storage and document identity (13.1). Snapshot fixtures recorded from the benchmark drawings for offline tests.

**Acceptance:** the checks find every known defect seeded in the reference drawings and report no false positives on the owner-approved ones; read-back meets section 16 on the benchmark.

### Phase 1b — Drawing pipeline on hand-modelled parts

- Shared IR core and bundle validation; Drawing Intent IR (with `context` fallback), Resolved Scheme (11.10.1) and Drawing Layout IR (planned/as-built, pins); read-only Part Feature Graph; ISO standard file, templates and profiles. No Design Intent or Assembly Graph IR is required.
- Tier 1 Read for every feature plus generic dimension read (5.3.2, ADR-029). Phase 1 geometry references (11.1).
- Pipeline 11.4: view planning, model-item insertion, cleanup, gap filling, tolerances/GD&T, placement engine, bounded re-layout (11.6). All of D1–D10.
- MCP tools 12.2 G, the document tools (12.2 A), `get_feature_tree`, `inspect_geometry`, toolsets, summary-first responses, CI token budget check (12.3). Fine-grained drawing tools in `detail` (11.9).

**Acceptance:** every hand-modelled benchmark part produces a drawing passing D1–D10; the holdout set is reported (11.8); failures report exact conflicts; no drawing with a failing check is reported done; every Tier 1 feature has a Read test; token budgets in 12.3 are met.

### Phase 1c — IR-built parts

- Compiler (section 6) and Create for the Tier 1 features the IR-built benchmark parts use; API verification (10.2 layer 1).
- `*_part_graph` tools, `list_feature_types` / `get_feature_schema`, `compile_bundle`, `execute_plan`.

**Acceptance:** every IR-built benchmark part builds, passes API verification and produces a drawing passing D1–D10; every Tier 1 feature it uses has a Create test.

## Phase 2 — Geometry References and Verification Foundation

- Semantic reference system (section 7), calibrated thresholds.
- Create for the rest of Tier 1 (5.3.2), with a Create test for every Tier 1 feature.
- Tier 2 feature coverage (5.3.3), each type tied to a CAD benchmark part.
- Assembly Graph IR v0 (5.6): components, hierarchy, standard mates; assembly cases in the CAD benchmark.
- API and geometry verification reports.
- CAD benchmark (30+ models); save/reopen/rebuild validation.
- Reference parity (2.4): the reference implementation's test scenarios rewritten as new tests; the remaining part and assembly tools.

**Acceptance:** ambiguous references are reported, never silently resolved; drawings re-checked correctly after model edits (11.7); invalid graphs rejected before execution; all rewritten reference scenarios pass, and the reference implementation can be retired.

## Phase 3 — Requirement Checks

- Implement the Design Intent IR minimum (4.3), then extend it toward the constraints needed for checks (4.4–4.5): requirement `limits`, and checking Drawing Intent specifications against them.
- Wall thickness, hole spacing, draft angle, clearance, interference checks.
- Verification reports with measured values per requirement.

**Acceptance:** violated requirements identified with measured vs expected values; unsupported analyses explicitly reported.

## Phase 4 — Incremental Editing and Recovery

- Graph diff, incremental compilation, CAD/IR synchronization, external-edit detection.
- Execution recovery (section 8.5).

**Acceptance:** upstream dimension changes handled predictably; unaffected features not resubmitted; external edits detected; failed executions diagnosed and safely recovered where possible.

## Phase 5 — Platform Expansion

Full Design Intent IR and natural-language interface, manufacturing intelligence, assembly/BOM expansion (mechanical mates, interfaces), motion studies, assembly drawings, additional drafting standards, additional CAD backends.
