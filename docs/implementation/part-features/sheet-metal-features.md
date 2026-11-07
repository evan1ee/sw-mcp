# Sheet Metal Features

Sheet metal parameters and features.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SMT-PAR — Sheet Metal Parameters

Thickness and bend defaults for a sheet metal body. Tier 1.

### Parameters

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-PAR-001` | Thickness | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `sheet_metal` |
| `SMT-PAR-002` | Bend radius | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `sheet_metal` |
| `SMT-PAR-003` | K-factor | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `sheet_metal` |
| `SMT-PAR-004` | Bend table | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `sheet_metal` |
| `SMT-PAR-005` | Relief type and size | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `sheet_metal` `relief` |
| `SMT-PAR-006` | Auto-relief options | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2; [5.7](../../../docs/architecture/feature-schema-guide.md) `sheet_metal` |
| SOLIDWORKS API | No member found by name search |
| Tests | — |
| Depends on | — |

## SMT-BAS — Base Flange / Tab

Creates the first sheet metal body or adds a tab. Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-BAS-001` | Base Flange / Tab (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SMT-BAS-002` | Profile and thickness direction | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-BAS-003` | Depth and end condition | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-BAS-004` | Tab merged into existing body | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-BAS-005` | Reverse direction | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IFeatureManager.InsertSheetMetalBaseFlange2` (19 params) ◐ |
| Tests | — |
| Depends on | [`SMT-PAR`](#smt-par--sheet-metal-parameters), [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |

## SMT-EDG — Edge Flange

Adds a flange to an edge. Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-EDG-001` | Edge Flange (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SMT-EDG-002` | Flange length and end condition | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-EDG-003` | Flange angle | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-EDG-004` | Flange position (material inside / outside / bend outside) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-EDG-005` | Bend radius override | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-EDG-006` | Relief | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-EDG-007` | Custom flange profile | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IFeatureManager.InsertSheetMetalEdgeFlange2` (13 params) ◐ |
| Tests | — |
| Depends on | [`SMT-BAS`](#smt-bas--base-flange--tab), edge references |

## SMT-SKB — Sketched Bend

Bends the sheet about a sketched line. Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-SKB-001` | Sketched Bend (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SMT-SKB-002` | Bend line, fixed face and position | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-SKB-003` | Bend angle and radius | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | No member found by name search |
| Tests | — |
| Depends on | [`SMT-BAS`](#smt-bas--base-flange--tab), [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |

## SMT-COR — Corners

Closed corner, break corner and relief. Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-COR-001` | Closed corner (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SMT-COR-002` | Closed corner (type and gap) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-COR-003` | Break corner / relief (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SMT-COR-004` | Break corner: chamfer | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-COR-005` | Break corner: fillet | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-COR-006` | Corner relief | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IModelDoc2.InsertSheetMetalClosedCorner` (0 params), `InsertSheetMetalBreakCorner` (2) ◐ |
| Tests | — |
| Depends on | [`SMT-BAS`](#smt-bas--base-flange--tab) |

## SMT-FLT — Flat Pattern

Flattens the sheet. Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-FLT-001` | Flat Pattern (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SMT-FLT-002` | Flatten state | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-FLT-003` | Corner treatment | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-FLT-004` | Fixed face selection | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | No member found by name search |
| Tests | — |
| Depends on | [`SMT-BAS`](#smt-bas--base-flange--tab) |

## SMT-ADV — Tier 2 and later Sheet Metal Features

Features beyond Tier 1.

### Create (Tier 2)

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-ADV-001` | Miter flange | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `SMT-ADV-002` | Hem | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `SMT-ADV-003` | Jog | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `SMT-ADV-004` | Hem types: closed, open, tear drop, rolled | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Read-only in Tier 1 (Create undecided)

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-ADV-005` | Unfold / fold | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `SMT-ADV-006` | Forming tools | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `SMT-ADV-007` | Louvers | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `SMT-ADV-008` | Gussets | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `SMT-ADV-009` | Convert to sheet metal | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `SMT-ADV-010` | Insert bends | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |

### Not named in the spec

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SMT-ADV-011` | Swept flange | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SMT-ADV-012` | Lofted bend | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2–5.3.3 |
| SOLIDWORKS API | `IFeatureManager.InsertSheetMetalMiterFlange` (14 params), `InsertSheetMetalHem2` (16), `InsertConvertToSheetMetal2` (10), `InsertSheetMetalGussetFeature3` (24), `InsertSheetMetalLoftedBend2` (10); `IModelDoc2.InsertSheetMetalJog` (7), `InsertSheetMetalFold` (0), `InsertSheetMetalUnfold` (0) ◐ |
| Tests | — |
| Depends on | [`SMT-BAS`](#smt-bas--base-flange--tab) |
