# Sketch Operations

Derived-geometry operations and excluded editing steps.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SK-OPS — Sketch Operations

Operations that derive sketch geometry. Spec §5.3.1 keeps interactive editing steps out of the IR: the agent states the resulting geometry.

### Tier 1 Create

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-OPS-001` | Offset entities | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 |
| `SK-OPS-002` | Offset: distance | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | SOLIDWORKS option; not named in the spec |
| `SK-OPS-003` | Offset: reverse direction | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | SOLIDWORKS option; not named in the spec |
| `SK-OPS-004` | Offset: select chain | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | SOLIDWORKS option; not named in the spec |
| `SK-OPS-005` | Offset: cap ends | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-OPS-006` | Offset: bidirectional | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-OPS-007` | Offset: convert result to construction geometry | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-OPS-008` | Convert entities | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 |
| `SK-OPS-009` | Convert: edges and faces | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | SOLIDWORKS option; not named in the spec |
| `SK-OPS-010` | Convert: select loop | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-OPS-011` | Mirror entities | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 `MirrorSketch` |
| `SK-OPS-012` | Mirror: about centerline or edge | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | SOLIDWORKS option; not named in the spec |
| `SK-OPS-013` | Mirror: keep original | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-OPS-014` | Sketch fillet (radius) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 |
| `SK-OPS-015` | Sketch chamfer: distance–distance | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 |
| `SK-OPS-016` | Sketch chamfer: angle–distance | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 |

### Patterns and curves

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-OPS-017` | Linear sketch pattern | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1; Create undecided |
| `SK-OPS-018` | Circular sketch pattern | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1; Create undecided |
| `SK-OPS-019` | Intersection curves | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | No spec statement |
| `SK-OPS-020` | Projected curves | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | No spec statement |

### Interactive editing steps

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-OPS-021` | Trim entities | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | Named in 5.3.1 |
| `SK-OPS-022` | Extend entities | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | Named in 5.3.1 |
| `SK-OPS-023` | Split entities | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | Named in 5.3.1 |
| `SK-OPS-024` | Move entities | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | An editing step by the principle of 5.3.1, which names only trim, extend and split |
| `SK-OPS-025` | Copy entities | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | An editing step by the principle of 5.3.1, which names only trim, extend and split |
| `SK-OPS-026` | Rotate entities | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | An editing step by the principle of 5.3.1, which names only trim, extend and split |
| `SK-OPS-027` | Scale entities | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | An editing step by the principle of 5.3.1, which names only trim, extend and split |
| `SK-OPS-028` | Stretch entities | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | An editing step by the principle of 5.3.1, which names only trim, extend and split |
| `SK-OPS-029` | Dynamic mirror | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | An editing step by the principle of 5.3.1, which names only trim, extend and split |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.1–5.3.2 |
| Tests | — |
| Depends on | `SK-ENT` |

**Notes and limitations**

- Trim, extend and split are excluded by 5.3.1. The other editing steps are Under Evaluation until the owner confirms the same principle applies.
