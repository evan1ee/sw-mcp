# ADR-054: Core architectural principles bind design decisions

- **Status:** Accepted (owner, 2026-11-04)
- **Source:** specification v1.23, section 1.3 (principles 12 and 13 added; 1, 3, 5, 6 and 7 sharpened)

## Context

Section 1.3 listed design principles, but nothing said they constrain later decisions, and two of the owner's long-term principles were missing: that the IR is the core of the system, and that failed runs are recovered from the actual model state. Without a binding rule, a convenient backend-shaped shortcut can erode them one decision at a time.

## Decision

The principles in 1.3 are binding. A design, schema, tool contract or implementation that conflicts with one needs an ADR that says which principle it departs from and why. The six long-term ones are:

1. **IR-first:** the IR is the core, not a wrapper around the SOLIDWORKS API.
2. **CAD-neutral semantics:** engineering meaning does not depend on SOLIDWORKS data structures.
3. **Deterministic execution:** same IR, initial model state and environment give reproducible results.
4. **Semantic references:** geometry is identified by meaning; face and edge indexes are never identity.
5. **Verifiable output:** geometry, dimensions, tolerances and drawings are checked against the specification, not only API success.
6. **Recoverability:** after an interruption the actual model state is determined first; operations are never blindly replayed.

## Rationale

Recording the rule once, with the exceptions route (an ADR), keeps the principles from being re-argued in each review and makes departures visible. Folding them into existing 1.3 numbers preserves references such as "principle 9".

## Consequences

- Reviews can cite a principle number. `AGENTS.md` points to 1.3.
- Existing deliberate departures stay as they are: the SOLIDWORKS-specific drawing cleanup (principle 1, **[Builder's call]**) is already documented.
- Principle 13 is only partly specified: 8.5 is P2 and the Phase 1a recovery rules cover jobs, not model edits. Revisit when Phase 4 starts.

## Where it applies

- [product-spec.md](../specifications/product-spec.md) — section 1.3
- [overview.md](../architecture/overview.md) — section 3
- [AGENTS.md](../../AGENTS.md) — section 2
