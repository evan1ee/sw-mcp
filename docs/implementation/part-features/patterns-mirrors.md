# Patterns and Mirrors

Pattern and mirror features.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## PAT-LIN — Linear Pattern

Repeats seed features along one or two directions. IR type `linear_pattern`.

### Direction 1

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-LIN-001` | Seed features (`seeds`) | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; ADR-074; `test_live_linear_pattern_plate` |
| `PAT-LIN-002` | Direction (`direction`) | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; ADR-074; `test_live_linear_pattern_plate` |
| `PAT-LIN-003` | Spacing | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; ADR-074; `test_live_linear_pattern_plate` |
| `PAT-LIN-004` | Instance count | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; ADR-074; `test_live_linear_pattern_plate` |
| `PAT-LIN-005` | Reverse direction | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Direction 2

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-LIN-006` | Direction 2 (`direction_2`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `pattern` |
| `PAT-LIN-007` | Direction 2 spacing and count | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-LIN-008` | Skip instances (`skip`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `pattern` |
| `PAT-LIN-009` | Geometry pattern (`geometry_pattern`) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `PAT-LIN-010` | Pattern bodies | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `PAT-LIN-011` | Vary sketch | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `PAT-LIN-012` | `instances` role | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3 `pattern`; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) |
| SOLIDWORKS API | `CreateDefinition(swFmLPattern)`, `ILinearPatternFeatureData` ● ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); `FeatureLinearPattern5` is obsolete |
| Tests | `tests/live/test_live_part_chain.py::test_live_linear_pattern_plate`, `tests/live/test_live_part_chain.py::test_live_direct_linear_pattern_ops` |
| Depends on | Seed features, direction references (K23) |

## PAT-CIR — Circular Pattern

Repeats seed features about an axis. IR type `circular_pattern`.

### Parameters

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-CIR-001` | Seed features | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; ADR-075; `test_live_circular_pattern_flange` |
| `PAT-CIR-002` | Axis (`direction`) | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; ADR-075; `test_live_circular_pattern_flange` |
| `PAT-CIR-003` | Angular spacing | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; degrees; ADR-075; `test_live_circular_pattern_flange` |
| `PAT-CIR-004` | Instance count | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 5.7.3 `pattern`; ADR-075; `test_live_circular_pattern_flange` |
| `PAT-CIR-005` | Equal spacing (`equal_spacing`) | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 22.5.2; ADR-075; `test_live_circular_pattern_flange` |
| `PAT-CIR-006` | Skip instances | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `pattern` |
| `PAT-CIR-007` | Geometry pattern | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `PAT-CIR-008` | Reverse direction | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3 `pattern`; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) |
| SOLIDWORKS API | `CreateDefinition(swFmCirPattern)`, `ICircularPatternFeatureData` ● ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); `FeatureCircularPattern5` is obsolete |
| Tests | `tests/live/test_live_part_chain.py::test_live_circular_pattern_flange`, `tests/live/test_live_part_chain.py::test_live_direct_circular_pattern_ops` |
| Depends on | Seed features, axis ([`RG-AXS`](reference-geometry.md#rg-axs--reference-axis)) |

## PAT-CRV — Curve Driven Pattern

Repeats seeds along a curve. Tier 2.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-CRV-001` | Curve and seeds | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `PAT-CRV-002` | Instance count or spacing | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `PAT-CRV-003` | Alignment (tangent / offset) | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3 |
| SOLIDWORKS API | `IFeatureManager.FeatureLocalCurveDrivenPattern` (13 params) ◐ |
| Tests | — |
| Depends on | Curve references |

## PAT-SKT — Sketch Driven Pattern

Repeats seeds at sketch points. Tier 2.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-SKT-001` | Sketch with points and seeds | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `PAT-SKT-002` | Reference point choice | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3 |
| SOLIDWORKS API | `IFeatureManager.FeatureSketchDrivenPattern` (2 params) ◐ |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) points |

## PAT-TBL — Table Driven Pattern

Repeats seeds at table coordinates. Read-only in Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-TBL-001` | Coordinate table and seeds | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Create undecided |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IFeatureManager.InsertTableDrivenPattern2` (5 params) ◐ |
| Tests | — |
| Depends on | Coordinate system [`RG-CSY`](reference-geometry.md#rg-csy--reference-coordinate-system) |

## PAT-FIL — Fill Pattern

Fills a region with pattern instances. Read-only in Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-FIL-001` | Region, layout and spacing | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Create undecided |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `IFeatureManager.FeatureFillPattern` (19 params) ◐ |
| Tests | — |
| Depends on | Region sketch |

## PAT-MIR — Mirror Feature and Mirror Body

Mirrors features or bodies about a plane. IR type `mirror`. The one authoritative mirror entry; `MBD` does not repeat it.

### Mirror

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `PAT-MIR-001` | Mirror features (`seeds`) | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 22.5.2; ADR-076; `test_live_mirror_plate` |
| `PAT-MIR-002` | Mirror plane (`plane`): standard plane | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 22.5.2; ADR-076; `test_live_mirror_plate` |
| `PAT-MIR-003` | Mirror plane: reference plane or planar face | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Needs [`RG-PLN`](reference-geometry.md#rg-pln--reference-plane), K28 |
| `PAT-MIR-004` | Merge result | In Scope | P1 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 22.5.2; ADR-076; `test_live_mirror_plate` |
| `PAT-MIR-005` | Geometry pattern | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `PAT-MIR-006` | Mirror Body | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3; bodies mark 256 ◐ |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) |
| SOLIDWORKS API | `IFeatureManager.InsertMirrorFeature2` ● ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); features mark 1, bodies 256, plane 2 |
| Tests | `tests/live/test_live_part_chain.py::test_live_mirror_plate`, `tests/live/test_live_part_chain.py::test_live_direct_mirror_ops` |
| Depends on | Standard plane, seed features |
