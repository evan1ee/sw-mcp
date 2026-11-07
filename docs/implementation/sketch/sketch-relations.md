# Sketch Relations

Geometric constraints.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SK-REL — Sketch Relations

Geometric constraints. A closed list is proposed in 22.4.2; none are in the schema yet.

### Relations

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-REL-001` | Coincident: point–point | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-002` | Coincident: point–curve | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-003` | Horizontal: line | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-004` | Horizontal: two points | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-005` | Vertical: line | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-006` | Vertical: two points | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-007` | Parallel | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-008` | Perpendicular | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-009` | Tangent: line–arc | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-010` | Tangent: arc–arc | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-011` | Concentric | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-012` | Equal: length | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-013` | Equal: radius | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-014` | Midpoint | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-015` | Symmetric (two points about a line) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-016` | Fix | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 closed list |
| `SK-REL-017` | Relation to the sketch origin (`origin`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 |
| `SK-REL-018` | Point addressing (`<entity>.start`, `.end`, `.center`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.2 |
| `SK-REL-019` | Collinear | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.4.2 |
| `SK-REL-020` | Coradial | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.4.2 |
| `SK-REL-021` | Pierce | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.4.2 |
| `SK-REL-022` | Merge points | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.4.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.4](../../../docs/specifications/ir-specification.md#224-sketch-model) §22.4.2, §22.4.4 |
| SOLIDWORKS API | `ISketch.RelationManager`, `ISketchRelationManager.AddRelation` with `swConstraintType_e` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); open question K27 |
| Tests | — |
| Depends on | [`SK-ENT`](sketch-entities.md#sk-ent--sketch-entities) |

**Notes and limitations**

- IR coordinates must already satisfy every relation (seed consistency, 22.4.4); whether the solver leaves them unmoved is unmeasured (K27).
- A sketch built without relations is natively under-defined.
