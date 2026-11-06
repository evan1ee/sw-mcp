# ADR-056: Multi-Stage Drawing Execution Pipeline and Closed-Loop Reconciliation

- **Status:** Proposed — Builder's call
- **Source:** specification v1.27, sections 6.5, 8.4, 11.4, 11.5, 11.6, 11.10, 11.11

## Context

Production drawing generation in CAD cannot be compiled into a monolithic, static operation plan upfront. Unlike 3D feature graphs where features are lowered in a predictable DAG, drawing annotations are dynamically imported and rendered by the CAD engine (`model_items.insert`). Determining which dimensions exist on the sheet, identifying duplicate model parameters across views, and detecting text overlaps requires reading back intermediate CAD geometry snapshots.

Furthermore, the existing implementation suffered from three architectural gaps:
1. Snapshot keys generated random GUIDs in C# (`ViewExtractor.cs` and `AnnotationExtractor.cs`), violating Spec §11.5.1 and breaking cache determinism.
2. The multi-stage execution sequence lived solely within an integration test script, lacking a production job orchestrator in `cad-application`.
3. Operations relied on ephemeral native CAD names (`"Drawing View1"`), leaking CAD session state and failing across localized installs.

## Decision

1. **Reject a Monolithic Drawing Plan IR:** The drawing pipeline will not introduce a static, upfront "Drawing Execution Plan IR" that duplicates `DrawingLayout`, `DrawingIntent`, and `OperationGroup`.
2. **Multi-Stage Orchestration via `ProduceDrawingRunner`:** Introduce `ProduceDrawingRunner` in `cad-application` driving the Spec §8.4 `produce_drawing` job lifecycle through sequential, inspectable `StagePlan` batches.
3. **Tri-Tier Identity Model:** Cleanly partition:
   - *Deterministic Snapshot Keys:* Canonical SHA-256 prefixes (`v_<hex10>`, `a_<hex10>`) per Spec §11.5.1 derived from canonical identity tuples.
   - *Semantic IDs:* CAD-neutral engineering references (`v_front`, parameter names) persisted via document-level view mapping (`sw_mcp_view_map`) and topological role binding.
   - *Native CAD IDs:* Ephemeral SOLIDWORKS COM strings scoped strictly to execution adapters.
4. **Strict Decoupling of Verification and Reconciliation:**
   - *Verification Engine:* Pure query evaluating hard checks D1–D10; outputs `DrawingReport` with failure primitives. Zero side-effects; never calls CAD APIs.
   - *Reconciliation Engine:* Pure solver calculating typed `CorrectionAction`s per Spec §11.6 priority rules. Zero CAD calls.
5. **Bounded Closed-Loop Execution:** Reconciliation is bounded to at most 8 iterations. Drawings are saved to final output paths (`.SLDDRW` / `.PDF`) only after entering `COMMITTED` (all required checks pass). Failed drawings are quarantined to `<name>.failed.SLDDRW` per ADR-046.

## Rationale

- **Physical Reality of CAD:** A closed-loop orchestrator matches how CAD systems actually work, preserving clean-room boundaries (ADR-010).
- **Auditability and Replay:** Decoupling immutable `StagePlan` from mutable `StageExecution` and append-only `ExecutionJournal` enables complete offline audit replay without CAD.
- **Zero Throwaway:** Preserves all existing pure planners (`plan_ortho_views`, `resolve_scheme_from_snapshot`, `plan_duplicate_cleanup`) and verified C# execution adapters.

## Consequences

- **What becomes easier:** AI agents can invoke `produce_drawing` via MCP as a reliable, cancellable job; snapshots become 100% deterministic and testable offline in CI; view references run identically across localized SOLIDWORKS installs.
- **What becomes harder:** The application layer must maintain the multi-stage state machine and stage plans rather than sending ad-hoc operation batches.
- **What must be revisited:** Direct `IAttribute` persistence on view features will be evaluated via technical spike S1; if superior, it will complement document custom property mapping.

## Where it applies

- [`docs/architecture/backend-operations.md`](../architecture/backend-operations.md) — section 6.5.3
- [`docs/architecture/execution-engine.md`](../architecture/execution-engine.md) — section 8.4
- [`docs/architecture/production-drawings.md`](../architecture/production-drawings.md) — sections 11.4, 11.5, 11.6, 11.11
- `packages/cad-application/src/cad_application/jobs/produce_drawing.py`
- `packages/cad-application/src/cad_application/drawing/stage_plan.py`
- `packages/cad-drawing/src/cad_drawing/reconciliation/`
- `apps/execution-server/ExecutionServer.Adapters/Drawings/`
