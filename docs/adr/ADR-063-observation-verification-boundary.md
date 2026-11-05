# ADR-063: Observation in the adapter, judgement in pure Python, and one evidence record

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.31, sections 8.8.9 and 8.9.6; architecture review F2, F6, F39. Extends ADR-007 and ADR-014

## Context

ADR-007 says verification is first-class, and 10.2.1 defines checks for the part chain. Still undefined: where comparison lives, whether a successful call may count as evidence, how missing data is expressed, what happens when a call took effect and then failed, and how a result is traced from an IR node to a native feature. The review showed what happens otherwise: fabricated read-back and checks that pass on unread data (F1 to F3).

## Decision

- **Adapter observers report raw facts**, in SI units, with a completeness state per collection: `present`, `empty`, `unavailable`, `unsupported`. Observers never compare, never rebuild, and never change a document.
- **Comparison is pure Python** in `cad-verification`, against values computed from the IR. The adapter fails an operation only when it can see the operation did not take effect, and postconditions are evaluated by the core.
- **Three outcomes are always separate:** `execution_status`, `rebuild_status`, `verification_status`. Missing data gives `not_evaluated`, which never counts as passed, and a required `not_evaluated` check fails the job.
- **Every failed operation states `details.effect`:** `none`, `applied` or `unknown`.
- **One evidence record per job,** a pure projection of plan, journal, results and observations. The journal remains the authority on what happened.
- **Reconciliation is one pure function** over the graph, the bindings, a read graph and measurements. It reports drift per feature and per measured quantity, never per face, and never merges automatically.

## Rationale

Independence is what makes verification evidence: if the same code builds and judges, it can agree with its own mistake. The split also lets every comparison run offline on recorded data. An explicit completeness state removes the ambiguity behind F2, and `effect` lets recovery tell "nothing happened" from "something may have happened". A projection avoids a second source of truth.

## Consequences

- Adds `schemas/execution-evidence/v0.json`, `details.effect`, one new error code (`PROPOSED_OPERATION_FAILED`), and a small growth of `part.measure`.
- K16: `expected_geometry` is exact only for narrow shapes. Fillets and similar features cannot rely on analytic values, so the verification level must be stated per node rather than implied.
- The ledger records an operation that may have taken effect and then failed (K17, closed by owner decision; rule in 8.7).
- The snapshot's drawing completeness work (F2) uses the same vocabulary when the freeze lifts.

## Where it applies

- [architecture/solidworks-adapter.md](../architecture/solidworks-adapter.md) — section 8.8.9
- [specifications/solidworks-adapter.md](../specifications/solidworks-adapter.md) — sections 8.9.5, 8.9.6, 8.9.9
- [architecture/verification-engine.md](../architecture/verification-engine.md) — section 10.2
