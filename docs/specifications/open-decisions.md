# Open Decisions and Missing Specifications

> Review of specification v1.11 (2026-11-03), updated for v1.23, for decisions that must be settled before implementation, so independent implementers build the same thing. Each item says why it matters, what is recommended, which document records it, and the first increment it blocks.

**Document types**
- **ADR** — a choice between real alternatives, recorded once (`docs/adr/`).
- **Spec** — a normative technical contract that code and tests are checked against (`docs/specifications/` or `docs/architecture/`).
- **Guideline** — how to implement, not what; can change without a spec version bump (`docs/development/`).

**Blocks:** `P0-schemas` (Phase 0 schema work), `1a`, `1b`, `1c`, or `later`.

Close an item by writing its document and linking it here; delete the item when the link is in place.

---

## Summary

Three open items, K3, J11 and J21. Every decision found in the v1.11 review is recorded below. New gaps found during implementation are added here in the same form: why it matters, the recommendation, the document type and the increment it blocks.

### K3: Reading title-block fields back from the owner's template (needs the owner's sheet format)

- **Why it matters.** D8 compares required fields against values read from the sheet. The mapping (13.3.4) says where a value comes *from* when filling, not where the add-in finds it when reading back. The way fields are located depends on the template (notes with property links, named blocks, sheet properties for scale and projection). The pure check D8 is built, but it cannot run on a real drawing until this is settled.
- **Also depends on the template:**
  - whether continuation sheets use their own format and carry the full 11.5.3 minimum (D8 now requires it on every sheet);
  - whether placeholder text the format ships with counts as empty;
  - whether the template has a revision table.
- **Recommendation.** When the owner supplies the sheet format, add a `read` locator per field to the mapping in 13.3.4, and calibrate D8 on it.
- **Document:** Spec (13.3.4, 11.5.3).
- **Blocks:** `1a` (live read-back only; the snapshot contract and D8 itself are not blocked).

### J11: The snapshot cannot say that a draft-quality view was switched for read-back

- **Why it matters.** 8.4 lets `check_drawing` switch draft-quality views to high quality in memory and says it reports that it did. Neither the `drawing.snapshot` result nor the snapshot schema (11.5.1) has a field for it, and the report's `warnings` are per annotation (11.5.4), so the fact cannot reach the job warnings (8.4). Milestone 5 carries the service-pack warning (from `HelloResult.warnings`) and leaves this one out rather than invent a field.
- **Recommendation.** When the adapter is built, add an optional per-view `quality_switched: true` to the snapshot's `View` (11.5.1), or a `warnings` list to the `drawing.snapshot` result (8.7), and map it to a `draft_view_switched` job warning. Decide with the live read-back, which shows whether the switch is per view or per sheet.
- **Document:** Spec (11.5.1 or 8.7, and 8.4).
- **Blocks:** `1a` (live read-back only).

### J21: The C# transcript harness cannot script an error response

- **Why it matters.** `check_drawing_bad_sheet.jsonl` has `drawing.snapshot` answer `IR_REFERENCE_UNRESOLVED`. The C# `ScriptedHandler` can only return results, so the scenario runs on the Python side only, and the add-in's error mapping for an unknown sheet (8.7) is not checked against the transcript.
- **Recommendation.** In milestone 6, let `ScriptedHandler` return a JSON-RPC error from the transcript frame, then set the scenario's `sides` to `["python", "csharp"]`. Test infrastructure only; no contract changes.
- **Document:** Spec (15.5) if the harness rule needs saying; otherwise none.
- **Blocks:** `1a` (C# side of one transcript).

---

## Closed

| ID | Item | Recorded in |
| --- | --- | --- |
| X1 | Process topology and job ownership across MCP clients | [ADR-041](../adr/ADR-041-core-service-topology.md) |
| I1 | One reference grammar | [§3.4.2](../architecture/shared-ir-core.md#342-references) |
| I2 | Canonical serialization, units and numeric comparison | [§3.4.3–3.4.4](../architecture/shared-ir-core.md#343-units-and-numbers) |
| I3 | Module identity, revisions and the bundle manifest | [§3.4.5](../architecture/shared-ir-core.md#345-documents-revisions-and-bundles) |
| V1 | Compatibility policy for every contract | [ADR-042](../adr/ADR-042-contract-compatibility.md) |
| M1 | Per-tool contracts (inputs, outputs, sync vs job) | [§12.4](../api/tool-contracts.md#124-tool-contracts) |
| M3 | Long-running job protocol over MCP | [ADR-043](../adr/ADR-043-jobs-over-mcp.md) |
| M4 | MCP protocol revision and features used | [ADR-044](../adr/ADR-044-mcp-protocol-baseline.md) |
| M5 | Projects, file roots and path authorization | [§12.5](../api/tool-contracts.md#125-projects-and-file-access) |
| S1 | SOLIDWORKS version and service-pack compatibility | [ADR-045](../adr/ADR-045-solidworks-version-compatibility.md) |
| S2 | Launcher, add-in startup and session-token handoff | [§8.6.1](../architecture/addin-runtime.md#861-loading-and-session-discovery) |
| S3 | Add-in threading, timeouts and UI-blocked detection | [§8.6.2–8.6.3](../architecture/addin-runtime.md#862-threading-and-dispatch) |
| S4 | Saving and restoring the engineer's SOLIDWORKS settings | [§8.6.4](../architecture/addin-runtime.md#864-engineer-settings-guard) |
| S5 | COM object lifetime in an in-process add-in | [Guideline G1](../development/implementation-guidelines.md#g1--com-objects-in-the-in-process-add-in) |
| E1 | Job journal format and Phase 1 crash semantics | [§13.2.3](../architecture/project-store.md#1323-job-journal) |
| E2 | Document ownership, save and output policy | [ADR-046](../adr/ADR-046-document-ownership-and-outputs.md) |
| X2 | Project store layout and atomicity | [§13.2](../architecture/project-store.md) |
| X3 | Configuration files and precedence | [§13.3](../architecture/configuration.md) |
| X4 | Python layer boundaries and the backend port | [Guideline G2](../development/implementation-guidelines.md#g2--python-layering-and-the-backend-port) |
| X5 | Structured logging and correlation | [Guideline G3](../development/implementation-guidelines.md#g3--logging-and-correlation) |
| T1 | Contract tests across MCP, IPC and schemas | [§15.5](../development/testing-strategy.md#155-contract-tests) |
| T2 | Test data, benchmark binaries and holdout custody | [ADR-047](../adr/ADR-047-test-data-custody.md) |
| T3 | Determinism and flake policy for tests | [§15.6](../development/testing-strategy.md#156-test-policy) |
| M2 | Passing IR to tools: by value or by store reference; update format | [ADR-048](../adr/ADR-048-ir-passing-and-patches.md) |
| C1 | Backend operation vocabulary and Execution Plan schema | [§6.5](../architecture/backend-operations.md) |
| C2 | Backend capability profile | [§6.6](../architecture/backend-operations.md#66-backend-capability-profile) |
| I4 | Validation error reporting | [§3.4.7](../architecture/shared-ir-core.md#347-validation-errors) |
| I5 | Feature-node schema conventions and defaults | [§5.7](../architecture/feature-schema-guide.md) |
| I6 | Read path: feature tree to read-only Part Feature Graph | [§5.8](../architecture/read-path.md) |
| C3 | Where geometry references are resolved | [ADR-049](../adr/ADR-049-reference-resolution-split.md) |
| C4 | Compiler stage behavior and error collection | [§6.7](../architecture/cad-compiler.md#67-stage-contract) |
| K1 | Geometric tests and thresholds for drawing checks D1–D3 (blocked 1a) | [§11.5.2](../architecture/production-drawings.md#1152-geometric-tests-for-d1d3-builders-call) |
| N1 | Schema file identity, and how a schema marks number kinds and unordered arrays for the canonical form (3.4.4) (blocked P0-schemas) | [§3.4.8](../architecture/shared-ir-core.md#348-schema-files-builders-call) |
| N2 | Drawing Geometry Snapshot encoding: keys for native items, curves, raw text boxes (blocked 1a) | [§11.5.1](../architecture/production-drawings.md#1151-drawing-geometry-snapshot-builders-call) |
| K2 | Rules for D5 without a Drawing Intent (closed chains, part results), D8 and D10, including save/reopen under a `check_drawing` that never saves (blocked 1a) | [§11.5.3](../architecture/production-drawings.md#1153-checks-without-a-drawing-intent-d5-d8-d10-builders-call) |
| N3 | Snapshot additions for dimension data, title block and rebuild state; hidden annotations not exported (blocked 1a) | [§11.5.1](../architecture/production-drawings.md#1151-drawing-geometry-snapshot-builders-call) |
| K4 | IPC message details: JSON-RPC error codes, handshake order, `ops.apply` and `drawing.snapshot` shapes, ledger, cancellation, chunks, transcript format (blocked 1a) | [§8.7](../architecture/execution-engine.md#87-ipc-messages-builders-call) |
| K5 | Generating contract types: the tool named in ADR-035 fails on the schemas and C# had no named tool; generated IPC types were unreachable from `cad-application` under G2 (blocked 1a) | [ADR-051](../adr/ADR-051-contract-type-generator.md), [G2](../development/implementation-guidelines.md#g2--python-layering-and-the-backend-port) |
| K6 | JSON library for the in-process add-in (blocked 1a) | [ADR-052](../adr/ADR-052-csharp-json-library.md) |
| R1 | Drawing report contents, verdict rule and how it states results are unverified (blocked P0-schemas) | [§11.5.4](../architecture/production-drawings.md#1154-drawing-report-builders-call) |
| J1 | Lifecycle: no path to ABORTED before RECOVERY, no QUEUED state, `queued_position` undefined, what each state means for `check_drawing`, whether FAILED is final in Phase 1 (blocked 1a) | [§8.4](../architecture/execution-engine.md#84-lifecycle) |
| J2 | Phase 1a tool contracts were an outline: exact inputs, outputs, errors, `drawing_intent` in 1a, sections, cursors, long-poll, cancel output, the code for invalid arguments and unknown tools (blocked 1a) | [§12.4.2, §12.4.5](../api/tool-contracts.md#1245-phase-1a-contracts), §8.7 (unknown sheets) |
| J3 | Which `ids` each tool returns, where the one-line summary is made, and the in-process result the transport will carry (blocked 1a) | [§12.4.2](../api/tool-contracts.md#1242-shared-conventions) |
| J4 | No schema for the contract files themselves; how CI compares them with the 12.4.4 table; annotation defaults (blocked 1a) | [§12.4.1, §12.4.4](../api/tool-contracts.md#1241-contract-file) |
| J5 | Store port, record contents, a drawing record for drawings the system did not make, lock, atomic writes, journal order and torn lines, recovery in 1a, retention references, finding a job by ID across stores (blocked 1a) | [§13.1](../architecture/data-management.md#131-storage-and-document-identity-builders-call), [§13.2](../architecture/project-store.md) |
| J6 | Threads or asyncio for the job engine, given a blocking IPC client; long-poll waits without wall-clock waits in tests; cancel from another thread (blocked 1a) | [ADR-053](../adr/ADR-053-job-engine-threading.md) |
| J7 | Configuration schema absent; error locations; where reading and validation live; loading title-block mappings without inventing one (blocked 1a) | [§13.3](../architecture/configuration.md) |
| J8 | Path checks as a pure function over a port; the code for a missing file (new `FILE_NOT_FOUND`); store folder hash (blocked 1a) | [§12.5](../api/tool-contracts.md#125-projects-and-file-access), [ADR-037](../adr/ADR-037-error-model.md) |
| J9 | Logging port and sink; where `request_id`, `job_id` and `operation_id` are made before the front-end exists (blocked 1a) | [G2, G3](../development/implementation-guidelines.md#g3--logging-and-correlation) |
| J10 | Job-level warnings (newer service pack, draft-view switch) cannot go in a report that is a pure function of its inputs (blocked 1a) | [§8.4](../architecture/execution-engine.md#84-lifecycle), [§11.5.4](../architecture/production-drawings.md#1154-drawing-report-builders-call); the draft-view part stays open as J11 |
| J12 | A relative `drawing.standard_dir` had nothing to resolve against (found in milestone 5) | [§13.3.3](../architecture/configuration.md) |
| J13 | No code for a file that exists but cannot be read, or for a store that cannot be read or written; an unexpected exception in a tool call had no defined answer (found in milestone 5) | [§12.5](../api/tool-contracts.md#125-projects-and-file-access), [§13.2.2](../architecture/project-store.md#1322-writing), [ADR-037](../adr/ADR-037-error-model.md) |
| J14 | An unknown tool name answered an envelope, against 12.4.2 (found in milestone 5) | [§12.4.2](../api/tool-contracts.md#1242-shared-conventions) |
| J15 | ADR-053 said the engine lock is never held across a file write; state changes do hold it (found in milestone 5) | [ADR-053](../adr/ADR-053-job-engine-threading.md) |
| J16 | Which `document.event` the job "did not cause" (found in milestone 5) | [§8.4](../architecture/execution-engine.md#84-lifecycle) |
| J17 | Closing the drawing after a lost, blocked, timed-out or user-interrupted job; a failed close (found in milestone 5) | [§8.4](../architecture/execution-engine.md#84-lifecycle) |
| J18 | Recovery edge cases: RECOVERY jobs, job folders without `job.json`, a store first opened after start, an unreadable known-stores list (found in milestone 5) | [§13.2.3](../architecture/project-store.md#1323-job-journal) |
| J19 | `elapsed_ms` before the job starts (found in milestone 5) | [§12.4.5](../api/tool-contracts.md#1245-phase-1a-contracts) |
| J20 | Log fields the engine emits that the sink's allow-list dropped (found in milestone 5) | [G3](../development/implementation-guidelines.md#g3--logging-and-correlation) |

## Recommended order

1. **Before Phase 0 schema work:** done (I1–I3 in §3.4, V1 in ADR-042).
2. **Before Phase 1a code:** done (ADR-041, ADR-043 to ADR-047, §8.6, §12.4–12.5, §13.2–13.3, §15.5–15.6, guidelines G1–G3).
3. **Before Phase 1b:** done (ADR-048, ADR-049, §3.4.7, §5.7, §5.8, §6.5–6.6).
4. **Before Phase 1c:** done (§6.7).

Owner input is still needed for ADR-034 to ADR-049 (all Proposed), assumptions A1–A14 and the holdout parts (11.8). The other Phase 0 owner decisions are recorded in [ADR-050](../adr/ADR-050-phase-0-owner-decisions.md).
