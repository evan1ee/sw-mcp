# Cut Features

Features that remove material.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## CF-EXT — Extruded Cut

Removes material by extruding a sketch profile. IR type `cut_extrude`; supports `blind` and `through_all_both`.

### Profile

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-EXT-001` | Circle profile (round hole) | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_blind_hole_in_top_face` |
| `CF-EXT-002` | Several circles in one sketch | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `plate_4h` fixture in `test_plate_end_to_end` |
| `CF-EXT-003` | Line-loop profile (rectangular pocket) | In Scope | P1 | Tested | ✅ | ✅ | ✅ | ⬜ | ✅ | ⬜ | `test_rectangular_through_cut_expected`, `test_rectangular_blind_cut_expected`; not run live |
| `CF-EXT-004` | Lines and circles mixed in one cut sketch | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec; refused today |
| `CF-EXT-005` | Several cut features sharing one sketch | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec; refused today |
| `CF-EXT-006` | Selected contours | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Sketch host

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-EXT-007` | Cut sketched on `plane:front` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `plate_4h` fixture in `test_plate_end_to_end` |
| `CF-EXT-008` | Cut sketched on `plane:top` / `plane:right` | In Scope | P1 | Implemented | ✅ | ✅ | ✅ | ⬜ | ✅ | ⬜ | Same adapter path; no dedicated test |
| `CF-EXT-009` | Cut sketched on `end_face` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `Dir=false`; `test_blind_hole_in_top_face` |
| `CF-EXT-010` | Cut sketched on `start_face` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_blind_hole_in_start_face` |
| `CF-EXT-011` | Cut sketched on a side face | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Refused (K28) |

### End condition

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-EXT-012` | Blind from a cap face | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_blind_hole_in_top_face`, `test_blind_hole_on_non_front_base_planes` |
| `CF-EXT-013` | Blind from `plane:front` | In Scope | P0 | Tested | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ | Live only via direct ops in `test_blind_cut_goes_into_body`, bypassing the compiler; no recorded run |
| `CF-EXT-014` | Through All Both from `plane:front` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `plate_4h` fixture in `test_plate_end_to_end` |
| `CF-EXT-015` | Through All Both from a cap face | In Scope | P1 | Tested | ✅ | ✅ | ✅ | ⬜ | ✅ | ⬜ | `test_through_hole_from_a_face_removes_the_full_depth`; not run live |
| `CF-EXT-016` | Through All, one direction (`through_all`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `CF-EXT-017` | Up To Next | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 |
| `CF-EXT-018` | Up To Surface | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 |
| `CF-EXT-019` | Offset From Surface | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `CF-EXT-020` | Mid Plane | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `CF-EXT-021` | Up To Vertex | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 5.7.3 |
| `CF-EXT-022` | Up To Body | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 5.7.3 |
| `CF-EXT-023` | Blind depth measured from the far face | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Limit noted in HANDOFF.md only; not named in the spec |

### Direction

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-EXT-024` | Blind cut from a cap face goes into the body | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Cap faces, `Dir=false`; `test_blind_hole_in_top_face` |
| `CF-EXT-025` | Reverse direction (`reverse`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `CF-EXT-026` | Flip side to cut (remove outside the profile) | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `FeatureCut4` `Flip`; not in the IR |
| `CF-EXT-027` | Two directions (`end_condition_2`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |

### Parameters and options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-EXT-028` | Depth (blind) in mm | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_blind_hole_in_top_face` (volume check) |
| `CF-EXT-029` | Draft angle and outward | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `CF-EXT-030` | Thin feature | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |
| `CF-EXT-031` | Feature scope | In Scope | P2 | Partially Implemented | ⬜ | ⬜ | ◐ | ⬜ | ⬜ | ⬜ | Adapter fixes `UseFeatScope=true` |
| `CF-EXT-032` | Auto-select bodies | In Scope | P2 | Partially Implemented | ⬜ | ⬜ | ◐ | ⬜ | ⬜ | ⬜ | Adapter fixes `UseAutoSelect=true` |
| `CF-EXT-033` | `end_face`, `side_faces` roles | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2; K30 |
| `CF-EXT-034` | Normal cut | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `FeatureCut4` `NormalCut`; not named in the spec |
| `CF-EXT-035` | Optimize geometry | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `FeatureCut4` `OptimizeGeometry`; not named in the spec |
| `CF-EXT-036` | Start condition: surface / vertex / offset | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `FeatureCut4` `T0`, `StartOffset`, `FlipStartOffset`; not named in the spec |

### Input rules

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-EXT-037` | Cut shapes strictly inside the base profile | In Scope | P1 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_cut_not_strictly_inside_base_rejected` |
| `CF-EXT-038` | Cut shapes do not overlap each other | In Scope | P1 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_overlapping_cut_features_rejected` |
| `CF-EXT-039` | Two cuts may not share one sketch | In Scope | P1 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_two_cuts_sharing_one_sketch_rejected` |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3–5.7.4; [ADR-070](../../../docs/adr/ADR-070-sketch-on-extrude-cap-face.md) |
| SOLIDWORKS API | `IFeatureManager.FeatureCut4` ✔ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); `swEndCondThroughAll` ✔ |
| IR / schema | [cut_extrude.json](../../../schemas/part-feature-graph/features/cut_extrude.json), [v0.json](../../../schemas/part-feature-graph/v0.json), [model.py](../../../packages/cad-ir/src/cad_ir/part_feature_graph/model.py) |
| Compiler | [lower.py](../../../packages/cad-compiler/src/cad_compiler/lowering/lower.py), [semantic.py](../../../packages/cad-compiler/src/cad_compiler/validator/semantic.py) |
| Adapter | [FeatureAdapter.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs) |
| Tests | [test_live_part_chain.py](../../../tests/live/test_live_part_chain.py), [test_live_part_ops.py](../../../tests/live/test_live_part_ops.py), [test_face_lowering.py](../../../packages/cad-compiler/tests/test_face_lowering.py), [test_part.py](../../../packages/cad-verification/tests/test_part.py) |
| Depends on | [`BF-EXT`](base-features.md#bf-ext--extruded-bossbase), [`SK-PLN`](../sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames), [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |

**Notes and limitations**

- Blind direction: from an origin plane the adapter passes `Dir=true`; from a cap face it passes `Dir=false` (`Dir=true` cuts nothing, `Flip=true` removes the outside). See 5.7.4.
- The adapter maps `through_all_both` to `FeatureCut4` with `T1=T2=swEndCondThroughAll` and `Sd=false`.
- A blind cut depth must be smaller than the base extrude depth (validator rule).

## CF-REV — Revolved Cut

Removes material by revolving a profile. IR type `cut_revolve`.

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-REV-001` | Profile and axis | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | See [`BF-REV`](base-features.md#bf-rev--revolved-bossbase) axis kinds |
| `CF-REV-002` | Blind angle / full 360 | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-REV-003` | Mid Plane | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-REV-004` | Reverse direction | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-REV-005` | Thin feature | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |
| `CF-REV-006` | Selected contours | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) §22.5.2 |
| SOLIDWORKS API | `FeatureRevolve2` with `IsCut` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)) |
| Tests | — |
| Depends on | [`BF-REV`](base-features.md#bf-rev--revolved-bossbase), [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |

**Notes and limitations**

- Options mirror [`BF-REV`](base-features.md#bf-rev--revolved-bossbase); the axis, angle and direction definitions are not repeated here.

## CF-SWP — Swept Cut

Removes material by sweeping a profile along a path. IR type `swept_cut`; Tier 2.

### Capability

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-SWP-001` | Profile and path | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-SWP-002` | Guide curves | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-SWP-003` | Twist | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-SWP-004` | Thin feature | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3 |
| SOLIDWORKS API | `CreateDefinition(swFmSweepCut)` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); `InsertCutSwept5` is obsolete |
| Tests | — |
| Depends on | [`BF-SWP`](base-features.md#bf-swp--swept-bossbase) |

**Notes and limitations**

- Inputs and options mirror [`BF-SWP`](base-features.md#bf-swp--swept-bossbase).

## CF-LFT — Lofted Cut

Removes material between two or more profiles. IR type `lofted_cut`; Tier 2.

### Capability

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-LFT-001` | Ordered profiles | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-LFT-002` | Guide curves and centerline | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `CF-LFT-003` | Thin feature | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3 |
| SOLIDWORKS API | `IFeatureManager.InsertCutBlend` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)) |
| Tests | — |
| Depends on | [`BF-LFT`](base-features.md#bf-lft--lofted-bossbase) |

**Notes and limitations**

- Inputs and options mirror [`BF-LFT`](base-features.md#bf-lft--lofted-bossbase).

## CF-BND — Boundary Cut

Removes material between boundary curves.

### Capability

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-BND-001` | Boundary cut | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `CF-BND-002` | Direction 2 curves | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | Not named in the spec |
| Tests | — |
| Depends on | [`BF-BND`](base-features.md#bf-bnd--boundary-bossbase) |

**Notes and limitations**

- Scope needs an owner decision.

## CF-SRF — Surface-Based Cuts

Removes material with a surface.

### Capability

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CF-SRF-001` | Cut with surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `CF-SRF-002` | Thicken cut | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | Not named in the spec |
| SOLIDWORKS API | Not searched; unverified |
| Tests | — |
| Depends on | [`SRF-OFF`](surface-features.md#srf-off--offset-surface) |

**Notes and limitations**

- Scope needs an owner decision.
