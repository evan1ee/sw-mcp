# ADR-061: The compiler and adapter meet only at schema contracts

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.31, section 8.9.1. Applies ADR-001, ADR-035 and G2 to the adapter

## Context

A design request for this adapter proposed C# interfaces such as `ICadDocument`, `ISketchAdapter` and `IFeatureInspector` as compiler-facing contracts, and described a C#/.NET compiler. The compiler is Python (ADR-001, Accepted, implemented in `packages/cad-compiler`), so it cannot consume C# interfaces. Contract ownership needs stating, so the two languages do not grow parallel abstractions.

## Decision

- **Compiler-facing contract:** the schemas in `schemas/ipc/` and `schemas/common/errors.json`, plus the capability profile (6.6). Python consumes them through generated types and the `Backend` port.
- **Compiler and job code never see** C# types, SOLIDWORKS names, positional arguments or selection marks.
- **C# interfaces are add-in internals.** `IOperationHandler` and `IReadCommandHandler` exist because the router and its tests need them. They carry no compatibility promise.
- **Per-domain or per-document C# interfaces are not created** until a second implementation exists.
- **The Python compiler stays (owner decision, 2026-11-05).** The owner confirmed this after the design request's "C#/.NET compiler" was raised. Moving the compiler to C# would be a new decision that supersedes ADR-001.

## Rationale

The process boundary already enforces the separation more strongly than interfaces could. A second interface layer with only one implementation adds indirection and invites COM objects to outlive commands (G1). Schema contracts are testable from both sides without SOLIDWORKS (15.5).

## Consequences

- Adding a feature changes a schema, a lowering rule and a handler. The port does not change.
- Generated contracts must stay able to express operation params. ADR-051's closed set may need extending for variant-typed params. If it cannot be, per-operation parameter models follow the precedent of the MVP's hand-written IR models, with a test against the schema.
## Where it applies

- [specifications/solidworks-adapter.md](../specifications/solidworks-adapter.md) — sections 8.9.1, 8.9.2, 8.9.8
- [architecture/backend-operations.md](../architecture/backend-operations.md) — sections 6.5, 6.6
- [development/implementation-guidelines.md](../development/implementation-guidelines.md) — G2
