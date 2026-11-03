# Open Decisions and Missing Specifications

> Review of specification v1.11 (2026-11-03), updated for v1.16, for decisions that must be settled before implementation, so independent implementers build the same thing. Each item says why it matters, what is recommended, which document records it, and the first increment it blocks.

**Document types**
- **ADR** — a choice between real alternatives, recorded once (`docs/adr/`).
- **Spec** — a normative technical contract that code and tests are checked against (`docs/specifications/` or `docs/architecture/`).
- **Guideline** — how to implement, not what; can change without a spec version bump (`docs/development/`).

**Blocks:** `P0-schemas` (Phase 0 schema work), `1a`, `1b`, `1c`, or `later`.

Close an item by writing its document and linking it here; delete the item when the link is in place.

---

## Summary

No open items. Every decision found in the v1.11 review is recorded below. New gaps found during implementation are added here in the same form: why it matters, the recommendation, the document type and the increment it blocks.

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

## Recommended order

1. **Before Phase 0 schema work:** done (I1–I3 in §3.4, V1 in ADR-042).
2. **Before Phase 1a code:** done (ADR-041, ADR-043 to ADR-047, §8.6, §12.4–12.5, §13.2–13.3, §15.5–15.6, guidelines G1–G3).
3. **Before Phase 1b:** done (ADR-048, ADR-049, §3.4.7, §5.7, §5.8, §6.5–6.6).
4. **Before Phase 1c:** done (§6.7).

Owner input is still needed for ADR-034 to ADR-049 (all Proposed), assumptions A1–A14 and the open Phase 0 owner decisions in section 18.
