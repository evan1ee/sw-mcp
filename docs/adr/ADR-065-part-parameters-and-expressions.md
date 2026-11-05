# ADR-065: Part parameters and expressions evaluate at compile time

- **Status:** Proposed
- **Source:** specification v1.35, section 22.8. Extends 4.6, which defers expressions, and 5.3.3

## Context

No Part Feature Graph value can depend on another today. Equations are Read-only in Tier 1 and Create in Tier 2 (5.3). Agents repeat derived numbers, and a change means editing every copy. The alternatives are to lower expressions to native SOLIDWORKS equations, to evaluate them in the compiler, or to leave them out.

## Decision

Add a graph-level `variables` collection, whose values or `expr` strings use a small closed grammar with dimensional checks. Any number field may hold `{ "expr": … }`. Expressions evaluate at compile time, in pure code, so plans and the wire carry only numbers. Native equations are not created. Schemas change only when a benchmark part needs this (ADR-018).

## Rationale

Compile-time evaluation keeps plans byte-deterministic, gives verification plain numbers, and needs no SOLIDWORKS equation API, which is unmeasured here. Native equations would make model behaviour depend on a second evaluator, and would make expected values depend on it. The cost is that a built part holds plain values, so an engineer who opens it cannot drive it through equations. Leaving expressions out is viable until a benchmark needs them.

## Consequences

- `variables` is the name, because `parameters` is already a node field (5.7.1).
- The evaluator is shared by compilation and contracts, so a bug there can agree with itself. It needs golden-value tests of its own.
- Creating native equations stays a separate Tier 2 decision, which this does not preclude.

## Where it applies

- [specifications/ir-specification.md](../specifications/ir-specification.md) — section 22.8
- [architecture/feature-schema-guide.md](../architecture/feature-schema-guide.md) — section 5.7.2
