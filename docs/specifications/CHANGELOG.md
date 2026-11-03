# Specification Changelog

Changes to the [specification](README.md), newest first.

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
