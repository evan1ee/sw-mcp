# ADR-058: A compiler-oriented semantic adapter, not a general SOLIDWORKS wrapper

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.31, section 8.8; extends ADR-009, ADR-018 and ADR-032

## Context

The compiler lowers an IR into operations, and something must turn those into SOLIDWORKS calls. The SOLIDWORKS API is very large, positional and stateful, and its calls depend on selection marks, edit mode and active-document state. Today's add-in has an `if` chain in `SwAddin.cs` with adapters of uneven quality (F6, F13). Options: direct calls from the compiler, a general wrapper, a thin COM abstraction, or a semantic adapter sized to the plans.

## Decision

The adapter implements only the operations and read commands that a compiled plan or a check needs, added when a feature needs them. Each operation is one handler that admits, translates, invokes, reads back and reports. Sketch entities, relations and dimensions are parts of `sketch.create`, not separate operations.

## Rationale

- Coverage tracks real need (ADR-018), so maintenance grows only with supported features.
- A general wrapper or thin abstraction would still leak selection and edit rules upward, and would do nothing for read-back or evidence.
- A pure translation stage in `ExecutionServer.Core` gives real offline tests of unit, direction and default rules. A mock of COM would not.
- Per-entity calls would break ADR-032, and a sketch edit must open and close within one command.

## Consequences

- **Easier:** `SwAddin.cs` shrinks to session setup. Unknown operations can no longer succeed. Native signatures live in one method each.
- **Harder:** each feature needs a handler, translator, observer, schema, live test and seeded-defect test.
- **Revisit:** when a second backend exists (principle 1.3(1)).
- Drawing adapters adopt this form only when the ADR-057 freeze lifts.

## Where it applies

- [architecture/solidworks-adapter.md](../architecture/solidworks-adapter.md) — sections 8.8.5, 8.8.6, 8.8.12
- [specifications/solidworks-adapter.md](../specifications/solidworks-adapter.md) — sections 8.9.3, 8.9.8
