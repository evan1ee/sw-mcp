# Product Specification

> Specification v1.28, sections 1, 2, 16, 20, 21. Index and section map: [specifications/README.md](../specifications/README.md).

## 1. Executive Summary

### 1.1 Vision

Build an AI-native Parametric CAD System that lets AI agents understand engineering requirements, build and modify parametric models, produce production-ready drawings, and verify engineering correctness through a structured, deterministic pipeline.

The system is not a translator from natural language to CAD API calls. It is an engineering-oriented layer between AI agents and native CAD systems.

**AI reasons about design intent. The CAD compiler turns intent into a parametric model. Native CAD executes geometry. The verification engine checks engineering correctness.**

### 1.2 Product Positioning

The system moves from *"an AI-driven SOLIDWORKS MCP"* to *"an engineering-aware parametric CAD platform"*. It is a **new, independent implementation**. The reference implementation's IR, compiler, executor and MCP tools are studied for behavior and lessons learned, but no code is copied from it.

The near-term measure of success is concrete: **a drawing produced by the system can be sent to a machine shop, mold maker or sheet metal shop without manual cleanup.**

The long-term differentiators are:

1. **Production-ready drawings** — complete, toleranced, cleanly laid out, verified automatically.
2. **Semantic geometry references** — references that survive edits and fail safely when ambiguous.
3. **Design intent verification** — checking engineering requirements, not only that CAD operations succeeded.
4. **Incremental parametric editing** — changing existing models without rebuilding them.

### 1.3 Core Design Principles

1. **CAD-neutral core:** core concepts and engineering semantics (the IR modules, compiler, references, checks) do not depend on a CAD vendor or its data structures, which keeps other CAD platforms possible. The drawing pipeline's cleanup and gap-filling steps are SOLIDWORKS-specific for now (model items, `MarkedForDrawing`, DimXpert) and sit in a clearly marked `solidworks` module of `cad-drawing`; a vendor-neutral interface for them is extracted when a second backend exists, not designed in advance **[Builder's call]**.
2. **Native CAD execution:** use the target CAD system's kernel and native features.
3. **Deterministic compilation and execution:** identical validated inputs and environment produce equivalent plans; given the same IR, initial model state and execution environment, execution gives predictable, reproducible results. Sources of nondeterminism (clocks, IDs, ordering, retries) are injected or canonicalized, never hidden.
4. **Explicit design intent:** engineering requirements are represented separately from modeling operations.
5. **Semantic geometry references:** identify geometry by meaning and context, not transient indexes. Face and edge indexes are at most a transient resolution result, never stored or relied on as identity (7).
6. **Closed-loop verification:** a successful API call does not mean a correct model or drawing. Output is verified against the intended specification: resulting geometry, dimensions, tolerances and engineering drawings (10, 11.5).
7. **Controlled execution:** CAD operations have an explicit lifecycle, state and failure handling (8.4, 8.5).
8. **Incremental modification:** update affected regions without rebuilding everything.
9. **Testability:** core logic is testable without a running CAD application.
10. **Extensibility:** backends, feature types and checks are independently extensible.
11. **Learn from the reference, don't copy it:** match the reference implementation's proven behavior where it works, and write all code new.
12. **IR-first architecture:** the IR is the core of the system, not a JSON wrapper around the SOLIDWORKS API. Engineering meaning lives in the IR modules (3.4, 4, 5, 11.10, 11.11); the compiler, references and verification are defined over the IR; a backend is a replaceable consumer of it. A capability is designed as IR semantics first, backend operations second (6.5).
13. **Recoverability:** after an interrupted or failed execution the system determines the actual model state (journal, before/after inspection, checkpoints) and recovers safely. It never blindly replays operations that may already have succeeded (8.5, 13.2).

These principles guide long-term design: implementation decisions, interface contracts, testing strategy and future extensions. A change that conflicts with one needs an ADR (19).

### 1.4 Goals, Non-goals, Anti-goals

**Goals (next release)**
- Production-ready ISO part drawings for machined, molded and sheet metal parts.
- Automated drawing checks that gate "done".
- A drawing benchmark that shows measurable improvement.

**Non-goals (next release)**
- Full Design Intent IR and natural-language-to-intent interface.
- Manufacturing rule engines (wall thickness, draft analysis) beyond what drawings need.
- Multi-CAD backends.
- Replacing the CAD kernel, FeatureManager, or professional engineering approval.

**Anti-goals — failure even if it "works"**
- A drawing reported as done that has crossing dimensions, missing dimensions or duplicates.
- Silently choosing an arbitrary face/edge when several are plausible.
- Reporting success when a required check failed.
- Building every subsystem at once and delaying a reliable foundation (overengineering).
- Losing a capability the reference implementation has (assemblies, drawings, sheet metal) without a deliberate decision. Until this system matches a capability, the reference implementation keeps serving it (2.4); the reference is retired only after parity.
- Copying code from the reference implementation.

---

## 2. System Scope

### 2.1 Priorities

| Capability | Description | Priority |
| --- | --- | --- |
| Production drawings | ISO part drawings: views, dimensions, tolerances, title block, automated layout checks | **P0** |
| Shared IR core + IR bundle | IDs, cross-module references, units, shared types, bundle validation (3.3) | **P0** |
| Design Intent IR (minimum, optional) | Functional features and requirements, process, material, treatment, manufacturing inputs, inspection requirements (4.3) | P2 |
| Assembly Graph IR v0 (optional) | Components, hierarchy, standard mates (5.6) | P1 |
| Drawing Intent IR | Critical dimensions, scheme overrides, tolerances/GD&T, datums, surface finish; plus the derived Resolved Scheme (11.10.1) | **P0** |
| Drawing Layout IR | Sheets, views, annotation placement, pins; planned and as-built | **P0** |
| Drawing benchmark | 10–20 reference parts with automated drawing checks | **P0** |
| Tier 1 feature coverage | Read support for all of Tier 1; Create only for what IR-built drawing benchmark parts need (5.3.2, ADR-029) | **P0** |
| Tier 1 Create (remainder) | Create support for the rest of Tier 1 | P1 |
| Token-efficient tool surface | Toolsets, on-demand schemas, summary responses, CI token budgets (12.3) | **P0** |
| Core platform (drawing path) | SOLIDWORKS executor (add-in, IPC, job model), read-only Part Feature Graph, drawing read-back; plus the compiler for the IR-built benchmark parts (Phase 1c) | **P0** |
| Core platform (reference parity) | Part/assembly tools at least at the reference implementation's capability level, all newly implemented. Reached by the end of Phase 2; until then the reference implementation serves those tasks (2.4) **[Builder's call]** | P1 |
| Semantic geometry references | References that survive edits; ambiguity fails safely | P1 |
| API verification | Operation success, feature status, rebuild errors for every executed plan (10.2 layer 1) | **P0** |
| Verification engine (geometry) | Structured geometry verification reports | P1 |
| Design intent verification | Wall thickness, hole spacing, draft, clearance | P2 |
| PMI output | Emit the Drawing Intent IR as SOLIDWORKS MBD / DimXpert 3D annotations | P2 **[Builder's call]** |
| Incremental compilation | Recompile affected dependencies only | P2 |
| Recovery engine | Diagnose and safely recover failed executions | P2 |
| Full Design Intent IR + natural-language interface | Constraints, parameters, relationships, checkable limits; derive drawing specifications from requirements | P3 |
| Manufacturing intelligence | Process-specific rule checks and suggestions | P3 |
| Assembly / BOM expansion | Mechanical mates, interfaces, BOM (5.6) | P3 |
| Motion studies | Motion drivers and studies in the Assembly Graph IR; needs SOLIDWORKS Motion (5.6) | P4 |
| Multi-CAD backend | Additional parametric CAD systems | P4 |

### 2.2 Out of Scope for the Initial Release

- Replacing a CAD geometry kernel or implementing a BREP engine.
- Replacing SOLIDWORKS FeatureManager.
- Arbitrary natural-language modeling without validation.
- Solving every engineering design problem or replacing engineering approval.
- Guaranteeing topology identity after arbitrary modifications.
- Assembly drawings beyond the reference implementation's level (matched, not improved yet).
- Drafting standards other than ISO (architecture must allow adding them later).

### 2.3 Reference Baseline

This is what the reference implementation does today, taken from the owner's comparison document. **Not yet verified**: Phase 0 confirms it. The table describes behavior to learn from and to match or exceed. It is not code to reuse.

| Area | Reference implementation | Target |
| --- | --- | --- |
| Design intent | AI planner generates Feature Graph directly | Task-driven IR modules (3.3): Part Feature Graph, Drawing Intent and Drawing Layout now; Assembly Graph in Phase 2; Design Intent in Phase 3 |
| Feature Graph IR | Implemented, JSON schema | Part Feature Graph IR: formalize further, keep its proven behavior |
| Compiler | Deterministic Python compiler | Multi-stage pipeline (section 6) |
| Geometry references | v0 resolver, geometric anchors | Semantic reference system (section 7) |
| Execution | C# COM/STA server, idempotency, state versioning | Explicit lifecycle and recovery (section 8) |
| Drawings | Drawing tools exist (e.g. `auto_dimension_drawing`, `dimension_drawing`, `move_drawing_dimension`); output not production-ready, dimensions cross | Production drawing pipeline (section 11) |
| Verification | Geometry comparison, rebuild checks | API + geometry + intent + drawing checks |
| Testing | Offline unit tests, live SOLIDWORKS tests | Plus drawing benchmark and CAD benchmark |

### 2.4 Coexistence and Migration [Builder's call]

The new system does not have to reach the reference implementation's capability level before it is useful. The two run side by side, which the distinct tool names (12.1) make safe:

- Both MCP servers can be connected to the same agent. Tasks the new system covers go to it; everything else (part modeling beyond the Phase 1 Create subset, assemblies, the reference's fine-grained tools) stays on the reference implementation.
- Both can drive the same SOLIDWORKS session. The reference implementation is not changed and cannot join the new system's job queue, so agent instructions say never to call both servers at once. If the reference touches a document a job is using, the add-in sees it as an outside edit and stops the job cleanly (8.3 rule 13).
- A capability moves to the new system when its rewritten reference test scenarios pass. The reference implementation is retired when all of them pass (end of Phase 2).

This keeps the anti-goal against losing capabilities (1.4) without making reference parity a Phase 1 prerequisite.

## 16. Performance and Quality Targets

Engineering goals, to be revised against real benchmarks.

| Area | Target |
| --- | --- |
| IR validation | < 100 ms typical |
| Compiler | < 500 ms typical, excluding CAD time |
| Drawing checks (D1–D10) | < 5 s per sheet excluding SOLIDWORKS read-back **[Builder's call]** |
| Drawing read-back | < 10 s per A3 sheet with up to 150 annotations, in process (8.2) **[Builder's call]**; measured in Phase 0 and revised |
| `produce_drawing` end to end | < 3 min per single-sheet benchmark part, including re-layout (11.6) **[Builder's call]**; a job that exceeds 10 min fails with its conflict list |
| MCP response | Execution ID returned for long operations |
| Traceability | Every operation has an ID |
| Reliability | No silent success on failed required operations or checks |
| References | Ambiguity fails safely |
| Drawings | No drawing reported done with a failing hard check |
| Token cost | Budgets in 12.3; tool definitions do not grow with feature coverage |
| Reproducibility | Every result records versions and inputs |

## 20. Definition of Done (production-ready release)

1. Stable, versioned contracts for the shared IR core and every IR module (Part Feature Graph, Assembly Graph, Design Intent, Drawing Intent, Drawing Layout).
2. Deterministic graph compilation.
3. Reliable native CAD execution and controlled COM lifecycle.
4. **Production drawings passing D1–D10 on the full drawing benchmark.**
5. Semantic geometry reference resolution with explicit ambiguity handling.
6. Model state synchronization.
7. Engineering constraint verification.
8. Structured, correlated execution logs.
9. Failure diagnosis and recovery.
10. Automated CAD and drawing regression tests.
11. Save/reopen/rebuild validation for parts and drawings.
12. Documented backend capabilities.
13. Backward-compatible MCP interfaces.
14. Reproducible benchmark results.

---

## 21. Final Product Definition

An engineering-aware CAD automation platform that lets AI agents understand design intent, build and modify parametric models, **produce drawings a shop can use without cleanup**, compile intent into native CAD operations, verify geometric and engineering correctness, and recover reliably from failures.

`Task → IR bundle (only the modules it needs) → CAD Compiler → Native Execution → Verification → Drawings / PMI where requested → Feedback`

The advantage does not come from exposing more CAD API calls to an agent. It comes from making AI-generated models and drawings reliable, editable, traceable and verifiably correct.
