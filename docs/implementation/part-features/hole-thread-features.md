# Hole and Thread Features

Hole Wizard, thread and cosmetic thread.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## HT-WIZ — Hole Wizard

Creates standard holes from a hole specification. IR type `hole_wizard`; ISO only (ADR-015).

### Hole type

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `HT-WIZ-001` | Simple (straight) hole | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `simple` |
| `HT-WIZ-002` | Counterbore | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `hole_spec` |
| `HT-WIZ-003` | Countersink | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `hole_spec` |
| `HT-WIZ-004` | Straight tap (tapped) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `tapped` |
| `HT-WIZ-005` | Tapered tap | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in `hole_spec` types |
| `HT-WIZ-006` | Slot hole types | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `HT-WIZ-007` | Legacy hole | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 |
| `HT-WIZ-008` | Advanced Hole | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `IFeatureManager.AdvancedHole2` (6 params) ◐; not named in the spec |

### Specification

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `HT-WIZ-009` | Standard: ISO | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ADR-015 |
| `HT-WIZ-010` | Other standards (ANSI, DIN, JIS, ...) | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | ADR-015 ISO-only |
| `HT-WIZ-011` | Size (e.g. `M6`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `hole_spec` |
| `HT-WIZ-012` | Fit: close / normal / loose | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `hole_spec` |
| `HT-WIZ-013` | Depth end condition | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `depth` as `end_condition` |
| `HT-WIZ-014` | Thread depth | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `hole_spec` |
| `HT-WIZ-015` | Cosmetic thread option | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | See [`HT-CTH`](#ht-cth--cosmetic-thread) |
| `HT-WIZ-016` | Near / far side countersink | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `HT-WIZ-017` | Counterbore / countersink dimensions override | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Placement

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `HT-WIZ-018` | Positions as sketch points | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Needs a sketch point; not named in the spec |
| `HT-WIZ-019` | Placement on a planar face | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Needs face references; not named in the spec |
| `HT-WIZ-020` | Placement on a cylindrical face | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `HT-WIZ-021` | Roles `cylindrical_face`, `axis`, `counterbore_face` | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.5 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2; [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3 `hole_spec` |
| SOLIDWORKS API | `IFeatureManager.HoleWizard5` ? ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); signature only, never run |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) (point), [`SK-PLN`](../sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames), [`BF-EXT`](base-features.md#bf-ext--extruded-bossbase) (body) |

**Notes and limitations**

- A simple round hole is **already available** as a circle cut: see [`CF-EXT`](cut-features.md#cf-ext--extruded-cut). That route is not a Hole Wizard feature and does not satisfy these rows.

## HT-THR — Thread

Modelled helical thread feature. Read-only in Tier 1; Create undecided.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `HT-THR-001` | Thread profile and location | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `HT-THR-002` | Thread start offset and end condition | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `HT-THR-003` | Right / left hand | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `HT-THR-004` | Cut vs boss thread | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | No member found by name search |
| Tests | — |
| Depends on | [`RG-CRV`](reference-geometry.md#rg-crv--reference-curves) helix, [`BF-SWP`](base-features.md#bf-swp--swept-bossbase) |

## HT-CTH — Cosmetic Thread

Annotation thread on a cylindrical face. Tier 1 Create and Read.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `HT-CTH-001` | Cosmetic thread (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `HT-CTH-002` | Standard and size | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `HT-CTH-003` | Blind or through depth | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `HT-CTH-004` | Major diameter | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `HT-CTH-005` | Thread class / tolerance | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `HT-CTH-006` | Linked to a Hole Wizard hole | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `cosmetic_thread` |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2; [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3 |
| SOLIDWORKS API | `IFeatureManager.InsertCosmeticThread3` (7 params) ◐ |
| Tests | — |
| Depends on | Edge or face references |
