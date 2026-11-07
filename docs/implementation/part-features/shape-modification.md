# Shape Modification

Fillet, chamfer, shell, draft, rib and related, plus the shared thin object.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SHP-FIL — Fillet

Rounds selected edges. IR type `fillet`; Tier 1 constant radius, Tier 2 variable and full-round.

### Type

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-FIL-001` | Constant radius | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1 |
| `SHP-FIL-002` | Variable radius | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 2 |
| `SHP-FIL-003` | Full round | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 2 |
| `SHP-FIL-004` | Face fillet | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 |
| `SHP-FIL-005` | Setback fillet | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Selection and options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-FIL-006` | Edge set by semantic reference (`edges`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Needs edge roles; K28 |
| `SHP-FIL-007` | Radius (`radius`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `SHP-FIL-008` | Propagate along tangent edges (`propagate`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `SHP-FIL-009` | Multiple radius | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-FIL-010` | Round corners / overflow handling | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-FIL-011` | `faces` role | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2–5.3.3; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) |
| SOLIDWORKS API | `CreateDefinition(swFmFillet)`, `ISimpleFilletFeatureData2.Initialize` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); `FeatureFillet3` is obsolete (ADR-068) |
| Tests | — |
| Depends on | [`BF-EXT`](base-features.md#bf-ext--extruded-bossbase) (body), edge references (K23, K28) |

**Notes and limitations**

- Needs `<node>.end_edges`-style edge roles, which the schema does not accept (K23).

## SHP-CHM — Chamfer

Bevels selected edges. IR type `chamfer`.

### Type

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-CHM-001` | Distance–distance | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `distance_distance` |
| `SHP-CHM-002` | Angle–distance | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `angle_distance` |
| `SHP-CHM-003` | Equal distance (single value) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `swChamferType_e` member; not in 22.5.2 |
| `SHP-CHM-004` | Vertex chamfer | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Excluded from Tier 1 |

### Selection and options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-CHM-005` | Edge set (`edges`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `SHP-CHM-006` | Propagate along tangent edges | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `SHP-CHM-007` | Flip direction | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-CHM-008` | `faces` role | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) (tagged `chamfer` object) |
| SOLIDWORKS API | `IFeatureManager.InsertFeatureChamfer` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)) |
| Tests | — |
| Depends on | Edge references (K23, K28) |

## SHP-SHL — Shell

Hollows a body, leaving walls of a given thickness.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-SHL-001` | Uniform thickness | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1 |
| `SHP-SHL-002` | Faces to remove | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-SHL-003` | Multi-thickness per face | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1 states uniform only |
| `SHP-SHL-004` | Shell outward | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-SHL-005` | Closed shell (no face removed) | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2; [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3 |
| SOLIDWORKS API | `IModelDoc2.InsertFeatureShell` (2 params) ◐ |
| Tests | — |
| Depends on | Face references (K28) |

## SHP-DFT — Draft

Tapers faces relative to a pull direction. IR type `draft`.

### Type

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-DFT-001` | Neutral plane | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1 |
| `SHP-DFT-002` | Parting line | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 2 |
| `SHP-DFT-003` | Step draft | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 2 |

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-DFT-004` | Draft angle | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-DFT-005` | Faces to draft | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-DFT-006` | Pull direction / reverse | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-DFT-007` | Face propagation (none, tangent, all, inner, outer) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2–5.3.3 |
| SOLIDWORKS API | `IModelDoc2.InsertMfDraft2` (5 params), `IFeatureManager.InsertMultiFaceDraft` (6 params) ◐ |
| Tests | — |
| Depends on | Face references (K28), [`RG-PLN`](reference-geometry.md#rg-pln--reference-plane) |

## SHP-RIB — Rib

Adds a thin supporting web from a sketch. Tier 1.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-RIB-001` | Rib (create) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SHP-RIB-002` | Sketch profile | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-RIB-003` | Thickness | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-RIB-004` | Thickness side: first, second or both | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `InsertRib` has `Is2Sided` and `ReverseThicknessDir` only; not named in the spec |
| `SHP-RIB-005` | Extrusion direction: parallel or normal to sketch | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-RIB-006` | Flip material side | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-RIB-007` | Draft angle | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-RIB-008` | Rib type: linear / natural | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-RIB-009` | Selected contours | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2; [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3 |
| SOLIDWORKS API | `IFeatureManager.InsertRib` (10 params) ◐ |
| Tests | — |
| Depends on | [`SK-PLN`](../sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames), [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |

## SHP-THN — Thin Feature (shared object)

The `thin` object used by extrude, cut, revolve, sweep and loft. Defined once here; feature sections only say whether they accept it.

### Thin object

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-THN-001` | One-side thickness (`one_side`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `SHP-THN-002` | Mid-plane thickness (`mid_plane`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `SHP-THN-003` | Two-side thickness (`two_side`, `thickness_2`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `SHP-THN-004` | Thickness value | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `SHP-THN-005` | Reverse thin direction | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-THN-006` | Cap ends | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-THN-007` | Auto-fillet corners | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-THN-008` | Thin feature on an open profile | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3 |
| SOLIDWORKS API | `IFeatureManager.FeatureExtrusionThin2` (30 params), `FeatureCutThin2` (29 params) ◐; `FeatureExtrusion3` has no thin arguments |
| Tests | — |
| Depends on | Hosts: [`BF-EXT`](base-features.md#bf-ext--extruded-bossbase), [`CF-EXT`](cut-features.md#cf-ext--extruded-cut), [`BF-REV`](base-features.md#bf-rev--revolved-bossbase), [`CF-REV`](cut-features.md#cf-rev--revolved-cut), [`BF-SWP`](base-features.md#bf-swp--swept-bossbase), [`CF-SWP`](cut-features.md#cf-swp--swept-cut), [`BF-LFT`](base-features.md#bf-lft--lofted-bossbase), [`CF-LFT`](cut-features.md#cf-lft--lofted-cut) |

## SHP-DOM — Dome

Adds a domed face. Tier 2.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-DOM-001` | Dome (create) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `SHP-DOM-002` | Distance and direction | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-DOM-003` | Reverse direction | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-DOM-004` | Elliptical dome | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-DOM-005` | Constraint point / direction | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SHP-DOM-006` | Continuous dome | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3 |
| SOLIDWORKS API | `IModelDoc2.InsertDome` (3 params) ◐ |
| Tests | — |
| Depends on | Face references |

## SHP-WRP — Wrap

Wraps a sketch on a face. Tier 3.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-WRP-001` | Emboss | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-WRP-002` | Deboss | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-WRP-003` | Scribe | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-WRP-004` | Thickness and reverse | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `IFeatureManager.InsertWrapFeature2` (5 params) ◐ |
| Tests | — |
| Depends on | Face references |

## SHP-FLX — Flex

Bends, twists, tapers or stretches bodies. Tier 3.

### Types

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-FLX-001` | Bending | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-FLX-002` | Twisting | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-FLX-003` | Tapering | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-FLX-004` | Stretching | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `IFeatureManager.InsertFlexFeature` (17 params) ◐ |
| Tests | — |
| Depends on | Body references |

## SHP-DEF — Deform

Deforms a body by point, curve-to-curve or surface push. Tier 3.

### Types

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-DEF-001` | Point deform | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-DEF-002` | Curve-to-curve | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-DEF-003` | Surface push | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | No member found by name search |
| Tests | — |
| Depends on | Body references |

## SHP-IND — Indent

Indents a target body with a tool body. Tier 3.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-IND-001` | Thickness and clearance | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-IND-002` | Keep tool body | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `IFeatureManager.InsertIndent` (6 params) ◐ |
| Tests | — |
| Depends on | [`MBD-ORD`](multi-body-features.md#mbd-ord--body-order-and-multi-body-rules) |

## SHP-SCL — Scale

Scales a body. Tier 3.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SHP-SCL-001` | Scale about centroid | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-SCL-002` | Scale about origin or coordinate system | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SHP-SCL-003` | Non-uniform scale | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `IFeatureManager.InsertScale` (5 params) ◐ |
| Tests | — |
| Depends on | Body references |
