# Base Features

Boss/base features that add material.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## BF-EXT — Extruded Boss/Base

Adds material by extruding a sketch profile. IR type `extrude`.

### Profile

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-EXT-001` | Closed line-loop profile on `plane:front` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` |
| `BF-EXT-002` | Closed line-loop profile on `plane:top` / `plane:right` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_blind_hole_on_non_front_base_planes` |
| `BF-EXT-003` | Single-circle profile | In Scope | P0 | Tested | ✅ | ✅ | ✅ | ⬜ | ✅ | ⬜ | Unit and benchmark `disc` in `test_score_part_ir_baseline_answers_passes_all_cases`; not run live |
| `BF-EXT-004` | Non-rectangular line-loop profile (e.g. L-shape) | In Scope | P1 | Tested | ✅ | ✅ | ✅ | ⬜ | ✅ | ⬜ | Benchmark `l_plate` in `test_score_part_ir_baseline_answers_passes_all_cases`; not run live |
| `BF-EXT-005` | Profile with inner contours (holes in the same sketch) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec; refused today |
| `BF-EXT-006` | Several disjoint profiles in one sketch | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Multi-body result; not named in the spec |
| `BF-EXT-007` | Selected contours | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-EXT-008` | Additional boss extrudes after the first | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Refused today; ADR-066 body order |

### End condition

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-EXT-009` | Blind | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `swEndCondBlind`; `test_plate_end_to_end` |
| `BF-EXT-010` | Through All (one direction) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | In 5.7.3; whether SOLIDWORKS supports it on a boss is unverified, needs a spike |
| `BF-EXT-011` | Through All, both directions (`through_all_both`) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | In 5.7.3; whether SOLIDWORKS supports it on a boss is unverified, needs a spike |
| `BF-EXT-012` | Up To Next | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `BF-EXT-013` | Up To Surface | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `BF-EXT-014` | Offset From Surface | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `BF-EXT-015` | Mid Plane | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `BF-EXT-016` | Up To Vertex | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 5.7.3 |
| `BF-EXT-017` | Up To Body | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 5.7.3 |
| `BF-EXT-018` | End-condition target (`GeometryRef`) and offset | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Needs references §7 / K23 |

### Direction

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-EXT-019` | One direction along the sketch normal | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Default; `test_plate_end_to_end` |
| `BF-EXT-020` | Reverse direction (`reverse`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3; adapter passes `Flip=false` |
| `BF-EXT-021` | Two directions (`end_condition_2`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `BF-EXT-022` | Direction 2 end condition | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `BF-EXT-023` | Direction 2 depth | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 |
| `BF-EXT-024` | Direction of extrusion by reference (non-normal) | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Parameters

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-EXT-025` | Depth (blind), positive, in mm | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `depth` above zero; `test_plate_end_to_end` |
| `BF-EXT-026` | Draft angle | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `draft.angle` |
| `BF-EXT-027` | Draft outward | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.3 `draft.outward` |
| `BF-EXT-028` | Start condition: sketch plane | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Default; `test_plate_end_to_end` |
| `BF-EXT-029` | Start condition: surface / vertex / offset | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `FeatureExtrusion3` `T0`, `StartOffset`; not named in the spec |
| `BF-EXT-030` | Depth as an equation or global variable | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 2; see [`CM-EQN`](common-and-document.md#cm-eqn--parameters-and-equations) |

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-EXT-031` | Thin feature | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |
| `BF-EXT-032` | Merge result | In Scope | P1 | Partially Implemented | ⬜ | ⬜ | ◐ | ⬜ | ⬜ | ⬜ | Adapter fixes `Merge=true`; no IR field |
| `BF-EXT-033` | Feature scope | In Scope | P2 | Partially Implemented | ⬜ | ⬜ | ◐ | ⬜ | ⬜ | ⬜ | Adapter fixes `UseFeatScope=true`; no IR field |
| `BF-EXT-034` | Auto-select bodies | In Scope | P2 | Partially Implemented | ⬜ | ⬜ | ◐ | ⬜ | ⬜ | ⬜ | Adapter fixes `UseAutoSelect=true`; no IR field |

### Output roles

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-EXT-035` | `start_face` role | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Used by cap-face sketches (ADR-070); `test_blind_hole_in_start_face` |
| `BF-EXT-036` | `end_face` role | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Used by cap-face sketches (ADR-070); `test_blind_hole_in_top_face` |
| `BF-EXT-037` | `side_faces` role | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Refused today (K23/K28); K30 |
| `BF-EXT-038` | `body` role | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.3; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) §22.5.2 |
| SOLIDWORKS API | `IFeatureManager.FeatureExtrusion3` ✔ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); `swEndConditions_e` (`swEndCondBlind` ✔; other members unverified) |
| IR / schema | [extrude.json](../../../schemas/part-feature-graph/features/extrude.json), [v0.json](../../../schemas/part-feature-graph/v0.json), [model.py](../../../packages/cad-ir/src/cad_ir/part_feature_graph/model.py) |
| Compiler | [lower.py](../../../packages/cad-compiler/src/cad_compiler/lowering/lower.py), [semantic.py](../../../packages/cad-compiler/src/cad_compiler/validator/semantic.py), [registry.py](../../../packages/cad-compiler/src/cad_compiler/registry.py) |
| Adapter | [FeatureAdapter.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs) |
| Tests | [test_live_part_chain.py](../../../tests/live/test_live_part_chain.py), [test_live_part_ops.py](../../../tests/live/test_live_part_ops.py), [test_rules.py](../../../packages/cad-compiler/tests/test_rules.py), [test_part.py](../../../packages/cad-verification/tests/test_part.py), [test_part_ir_benchmark.py](../../../tests/cad-benchmark/test_part_ir_benchmark.py) |
| Depends on | [`SK-PLN`](../sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames), [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities), [`SK-VAL`](../sketch/sketch-validation.md#sk-val--sketch-validation) |

**Notes and limitations**

- The adapter hard-codes `Sd=true`, `Flip=false`, `Dir=false`, `Merge=true`, `UseFeatScope=true`, `UseAutoSelect=true`, no draft, no thin. Those settings are not IR fields.

## BF-REV — Revolved Boss/Base

Adds material by revolving a profile about an axis. IR type `revolve`.

### Profile and axis

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-REV-001` | Profile from a sketch | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1 |
| `BF-REV-002` | Axis: sketch centerline | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `axis`; mark 4 or 16 ◐ |
| `BF-REV-003` | Axis: sketch line | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-REV-004` | Axis: model edge | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Needs edge references (K28); not named in the spec |
| `BF-REV-005` | Axis: reference axis | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `axis` role |
| `BF-REV-006` | Selected contours | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Angle and direction

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-REV-007` | Blind angle (0 to 360) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `angle` |
| `BF-REV-008` | Full 360 degrees | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `angle` up to 360 |
| `BF-REV-009` | Mid Plane | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `mid_plane` |
| `BF-REV-010` | Reverse direction | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `reverse` |
| `BF-REV-011` | Two directions (direction 2 angle) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.5.2 |
| `BF-REV-012` | Up To Vertex / Surface / Body | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Mark 32 ◐; not in 22.5.2 |

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-REV-013` | Thin feature | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |
| `BF-REV-014` | Merge result | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `merge_result` |
| `BF-REV-015` | `faces_by_axial_order` role | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `BF-REV-016` | `body` role | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) §22.5.2; roadmap A5 |
| SOLIDWORKS API | `IFeatureManager.FeatureRevolve2` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); angles in radians |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities), [`RG-AXS`](reference-geometry.md#rg-axs--reference-axis) |

**Notes and limitations**

- `cut_revolve` is a separate IR type ([`CF-REV`](cut-features.md#cf-rev--revolved-cut)) although SOLIDWORKS uses one call with `IsCut`.

## BF-SWP — Swept Boss/Base

Adds material by sweeping a profile along a path. IR type `sweep`; Tier 2.

### Inputs

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-SWP-001` | Profile | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `profile` |
| `BF-SWP-002` | Path (sketch curve) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `path` |
| `BF-SWP-003` | Path from model edges / curve feature | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-SWP-004` | Guide curves | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `guides` |
| `BF-SWP-005` | Centerline guide | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Orientation and shape

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-SWP-006` | Twist | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `twist` |
| `BF-SWP-007` | Orientation: follow path | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Sweep orientation not in 22.5.2 |
| `BF-SWP-008` | Orientation: keep normal constant | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-SWP-009` | Orientation: follow path and guide curve | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-SWP-010` | Start / end tangency | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-SWP-011` | Thin feature | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |
| `BF-SWP-012` | Merge result | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `BF-SWP-013` | `start_face`, `end_face` roles | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `BF-SWP-014` | `body` role | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) §22.5.2 |
| SOLIDWORKS API | `CreateDefinition(swFmSweep)`, `ISweepFeatureData`, `CreateFeature` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); `InsertProtrusionSwept4` is obsolete (ADR-068) |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities), [`SK-PLN`](../sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames) |

**Notes and limitations**

- Selection marks: profile 1, path 4, guide 2, direction 128 (◐). Needed by the CAD benchmark spring (Helix + Sweep).

## BF-LFT — Lofted Boss/Base

Adds material by blending two or more profiles. IR type `loft`; Tier 2.

### Inputs

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-LFT-001` | Ordered profiles (two or more) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `profiles` |
| `BF-LFT-002` | Guide curves | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `guides` |
| `BF-LFT-003` | Centerline | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `centerline` |
| `BF-LFT-004` | Closed loft (last profile joins first) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `closed` |
| `BF-LFT-005` | Start / end constraints (tangent, normal) | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-LFT-006` | Connector adjustment | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

### Options

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-LFT-007` | Thin feature | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 `thin`; options defined in [`SHP-THN`](shape-modification.md#shp-thn--thin-feature-shared-object), this row tracks only this feature's support |
| `BF-LFT-008` | Merge result | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |
| `BF-LFT-009` | `start_face`, `end_face`, `body` roles | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.5.2 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3; [22.5](../../../docs/specifications/ir-specification.md#225-feature-model) §22.5.2 |
| SOLIDWORKS API | `IFeatureManager.InsertProtrusionBlend2` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); selection order sets direction |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities), [`SK-PLN`](../sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames), [`RG-PLN`](reference-geometry.md#rg-pln--reference-plane) |

**Notes and limitations**

- Profiles must be closed for a solid result (◐).

## BF-BND — Boundary Boss/Base

Adds material between boundary curves in one or two directions.

### Capability

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `BF-BND-001` | Boundary boss with direction 1 curves | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-BND-002` | Direction 2 curves | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-BND-003` | Tangency and influence options | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `BF-BND-004` | Merge result | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | Not named in the spec |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |

**Notes and limitations**

- Not in any tier of 5.3; scope needs an owner decision.
