# ADR-066: The order of body-changing features is explicit in the graph

- **Status:** Proposed
- **Source:** specification v1.35, section 22.7.2; found while reviewing 5.7.1 against `cad_compiler/graph/analyze.py`

## Context

Nodes build in topological order, with ties broken by node ID (5.7.1). Feature order changes geometry, but references do not capture it: a through-all cut refers only to its sketch. Without a declared edge, a cut could build before its boss, and the outcome would depend on how the IDs are spelled. The MVP masks this with two special rules: one extrude only, and each cut must depend on it. They cannot survive a second boss.

The options are an explicit `sequence` field, which 3.4.1 allows where order matters; implied edges from each body-changing node to the previous in ID order, which keeps the problem; or requiring a path between such nodes.

## Decision

Nodes whose type changes a body must be totally ordered by the graph. For any two of them a directed path must exist, otherwise `IR_RULE_VIOLATED` names both. Sketches and reference geometry stay free, and the ID tie-break orders only them. This replaces the MVP's two rules.

## Rationale

It adds no field, reuses `dependencies`, and turns a silent dependence on spelling into an actionable error. A `sequence` field would duplicate the graph and could contradict it. A partial order over independent bodies might be safe, but proving commutativity is not worth it.

## Consequences

- Agents state one more dependency per solid node, as the plate fixture already does.
- Reordering becomes visible in a graph diff, as a dependency change.
- Multibody parts with independent bodies still need an order, which costs nothing.
- `feature_contracts` can rely on a single body history.

## Where it applies

- [specifications/ir-specification.md](../specifications/ir-specification.md) — section 22.7.2, 22.9.2
- [architecture/feature-schema-guide.md](../architecture/feature-schema-guide.md) — section 5.7.1
