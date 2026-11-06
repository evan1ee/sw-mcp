# ADR-069: Plan-local operation IDs come from the node

- **Status:** Proposed
- **Source:** specification v1.35, section 23.4.4; found comparing 8.9.6 with `cad_compiler/lowering/lower.py`

## Context

Plan-local operation IDs are `op_<sequence>`. Adding one node renumbers all later operations, so plan diffs are noisy, and an incremental plan (section 9) could not refer to an operation of an earlier plan. The evidence example in 8.9.6 already shows `op_extrude_base`, so the documents and the code disagree.

## Decision

A plan-local ID is `op_<node_id>`. An operation that implements no node takes a fixed name, such as `op_part_create`. If a node ever lowers to several operations, they take `op_<node_id>_<n>`. `sequence` still decides order, and the wire ID stays `<job_id>:<sequence>` (13.2.3).

## Rationale

Node IDs are already stable, unique and never reused (3.4.1), and the join to `source` becomes obvious. The ID grammar leaves room for the prefix only up to its 64-character limit, so a node ID longer than 61 characters needs a rule: it fails `COMPILE_PLAN_INVALID`, since no real node needs that length.

## Consequences

- Changes every plan hash and the golden plan. At major 0 this needs only a `feature_lowering` stage bump (6.7.4).
- Inserting a node no longer renames other operations. Their `sequence` values still shift, so a plan's hash still changes.

## Where it applies

- [specifications/compiler-architecture-specification.md](../specifications/compiler-architecture-specification.md) — section 23.4.4
- [architecture/backend-operations.md](../architecture/backend-operations.md) — section 6.5.3
