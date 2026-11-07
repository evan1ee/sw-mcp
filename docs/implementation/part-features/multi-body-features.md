# Multi-Body Features

Combine, split, delete/keep, move/copy, intersect and body order.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## MBD-CMB — Combine Bodies

Merges bodies. Tier 1 Create.

### Operations

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `MBD-CMB-001` | Combine bodies (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `MBD-CMB-002` | Add | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `MBD-CMB-003` | Subtract | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `MBD-CMB-004` | Common | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `MBD-CMB-005` | Body selection by role | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IFeatureManager.InsertCombineFeature` (3 params) ◐ |
| Tests | — |
| Depends on | [`MBD-ORD`](#mbd-ord--body-order-and-multi-body-rules) |

## MBD-SPL — Split Body

Splits a body into several. Read-only Tier 1, Create Tier 2.

### Operations

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `MBD-SPL-001` | Split body (create) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `MBD-SPL-002` | Split by plane | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `MBD-SPL-003` | Split by surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `MBD-SPL-004` | Resulting bodies kept or discarded | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2–5.3.3 |
| SOLIDWORKS API | `IFeatureManager.PreSplitBody2`, `PostSplitBody2` (5 params) ◐ |
| Tests | — |
| Depends on | [`RG-PLN`](reference-geometry.md#rg-pln--reference-plane) |

## MBD-DEL — Delete / Keep Body

Removes or keeps bodies. Tier 1 Create (delete).

### Operations

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `MBD-DEL-001` | Delete body | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `MBD-DEL-002` | Keep selected bodies | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IFeatureManager.InsertDeleteBody2` (1 param, `KeepBodies`) ◐ |
| Tests | — |
| Depends on | [`MBD-ORD`](#mbd-ord--body-order-and-multi-body-rules) |

## MBD-MOV — Move / Copy Body

Transforms or copies a body. Read-only in Tier 1.

### Operations

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `MBD-MOV-001` | Translate body | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Create undecided |
| `MBD-MOV-002` | Rotate body | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `MBD-MOV-003` | Copy body | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IFeatureManager.InsertMoveCopyBody2` (12 params) ◐ |
| Tests | — |
| Depends on | — |

## MBD-INT — Intersect

Creates bodies from intersecting geometry. Not named in the spec.

### Operations

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `MBD-INT-001` | Intersect bodies / surfaces | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | Not named in the spec |
| SOLIDWORKS API | `IFeatureManager.PreIntersect2` (2 params), `PostIntersect` (3) ◐ |
| Tests | — |
| Depends on | — |

## MBD-ORD — Body Order and Multi-Body Rules

How several bodies are ordered and verified. Mirror body is [`PAT-MIR`](patterns-mirrors.md#pat-mir--mirror-feature-and-mirror-body); merge-result flags live in each feature.

### Rules

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `MBD-ORD-001` | Explicit body order between body-changing nodes | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ADR-066 Proposed; today one extrude only |
| `MBD-ORD-002` | Verification of more than one solid body | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ADR-066; expected geometry assumes one body |
| `MBD-ORD-003` | `body` role for body selection | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [ADR-066](../../../docs/adr/ADR-066-body-order-is-explicit.md) (Proposed) |
| SOLIDWORKS API | — |
| Tests | — |
| Depends on | — |
