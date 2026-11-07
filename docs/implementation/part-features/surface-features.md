# Surface Features

Surface creation, trimming and thickening.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SRF-OFF — Offset Surface

Offsets a surface. Tier 3.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SRF-OFF-001` | Offset distance and direction | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-OFF-002` | Multiple faces | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `IModelDoc2.InsertOffsetSurface` (2 params) ◐ |
| Tests | — |
| Depends on | Face references |

## SRF-KNT — Knit Surface

Joins surfaces into one. Tier 3.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SRF-KNT-001` | Knit surfaces | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-KNT-002` | Create solid from enclosed volume | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-KNT-003` | Merge entities / gap control | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | No member found by name search |
| Tests | — |
| Depends on | — |

## SRF-TRM — Trim Surface

Trims a surface with a tool. Tier 3.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SRF-TRM-001` | Standard trim (tool) | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-TRM-002` | Mutual trim | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-TRM-003` | Keep or remove selections | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `IFeatureManager.PreTrimSurface` (4 params), `PostTrimSurface` (1) ◐ |
| Tests | — |
| Depends on | — |

## SRF-THK — Thicken

Turns a surface into a solid. Tier 3. The one authoritative thicken entry.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SRF-THK-001` | Thickness side 1 / side 2 / both | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-THK-002` | Thickness value | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-THK-003` | Merge result | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SRF-THK-004` | Create solid from enclosed volume | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `IFeatureManager.FeatureBossThicken` (7 params) ◐ |
| Tests | — |
| Depends on | [`SRF-KNT`](#srf-knt--knit-surface) |

## SRF-CRE — Surface Creation

Surface counterparts of boss features. Not named in the spec.

### Types

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SRF-CRE-001` | Extruded surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-002` | Revolved surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-003` | Swept surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-004` | Lofted surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-005` | Boundary surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-006` | Planar surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-007` | Fill surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-008` | Ruled surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-009` | Extend surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-010` | Untrim surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SRF-CRE-011` | Mid surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | Not named in the spec |
| SOLIDWORKS API | `IFeatureManager.InsertUntrimSurface2` (5 params) ◐ for untrim; others not found by name search |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |
