# Sketch Management

Placement, frames and lifecycle of sketches.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SK-PLN — Sketch Placement and Coordinate Frames

Which plane or face a sketch can be placed on, and the frame its 2D coordinates use.

### Sketch host

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-PLN-001` | Sketch on `plane:front` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` |
| `SK-PLN-002` | Sketch on `plane:top` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_blind_hole_on_non_front_base_planes` |
| `SK-PLN-003` | Sketch on `plane:right` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_blind_hole_on_non_front_base_planes` |
| `SK-PLN-004` | Sketch on `<extrude>.end_face` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ADR-070, all three base planes; `test_blind_hole_in_top_face`, `test_blind_hole_on_non_front_base_planes` |
| `SK-PLN-005` | Sketch on `<extrude>.start_face` | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ADR-070, mirrored frame; `test_blind_hole_in_start_face`, `test_blind_hole_on_non_front_base_planes` |
| `SK-PLN-006` | Sketch on a side face (`<node>.side_faces`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Blocked by K23/K26/K28; refused today |
| `SK-PLN-007` | Sketch on a face created by a cut | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `cut_extrude` roles `end_face`, `side_faces` (22.5.2); refused today |
| `SK-PLN-008` | Sketch on a reference-plane node | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Needs [`RG-PLN`](../part-features/reference-geometry.md#rg-pln--reference-plane); 22.3.4 |
| `SK-PLN-009` | Sketch on an arbitrary planar face by semantic reference | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Geometry references §7; only cap faces resolved today |

### Frames and units

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-PLN-010` | Standard planes located by order and normal, not display name | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Every live job uses `RefPlane` order and normal, e.g. `test_plate_end_to_end`; a localized install is not tested |
| `SK-PLN-011` | Cap-face sketch axes checked against the stated frame | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Every cap-face live job; `CapFaceSketch.Verify`; `test_blind_hole_on_non_front_base_planes` |
| `SK-PLN-012` | 2D coordinates in millimetres (`units: mm`) | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `PartUnits` metre conversion; `test_plate_end_to_end` |
| `SK-PLN-013` | 2D coordinates in inches (`units: in`) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | K24; schema `units` is `const: mm` |
| `SK-PLN-014` | Sketch origin offset on the host | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-PLN-015` | Standard-plane normal checked against its role | In Scope | P0 | Implemented | N/A | N/A | ✅ | ✅ | ⬜ | ⬜ | `SketchAdapter`; failure path tested only by `test_template_with_reordered_planes`, which can skip |
| `SK-PLN-016` | Frame mismatch raises `REF_SIGNATURE_MISMATCH` | In Scope | P1 | Implemented | N/A | N/A | ✅ | ⬜ | ⬜ | ⬜ | `FaceSignatureTests` cover `FrameMatches` only; no test reaches the raise |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.4; [ADR-070](../../../docs/adr/ADR-070-sketch-on-extrude-cap-face.md) |
| SOLIDWORKS API | `IFeature.Select2`, `ISketchManager.InsertSketch` ✔ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)) |
| IR / schema | [sketch.json](../../../schemas/part-feature-graph/features/sketch.json), [model.py](../../../packages/cad-ir/src/cad_ir/part_feature_graph/model.py), [faces.py](../../../packages/cad-ir/src/cad_ir/part_feature_graph/faces.py), [planes.py](../../../packages/cad-ir/src/cad_ir/part_feature_graph/planes.py) |
| Compiler | [lower.py](../../../packages/cad-compiler/src/cad_compiler/lowering/lower.py), [semantic.py](../../../packages/cad-compiler/src/cad_compiler/validator/semantic.py) |
| Adapter | [SketchAdapter.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs), [CapFaceSketch.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/CapFaceSketch.cs) |
| Tests | [test_live_part_chain.py](../../../tests/live/test_live_part_chain.py), [test_face_sketch.py](../../../packages/cad-compiler/tests/test_face_sketch.py), [test_face_lowering.py](../../../packages/cad-compiler/tests/test_face_lowering.py) |
| Depends on | — |

**Notes and limitations**

- Only `<extrude>.start_face` and `<extrude>.end_face` are accepted as face hosts; side faces, cut faces and edges are refused by the validator (K23, K26, K28).

## SK-LIF — Sketch Lifecycle and State

Creating, editing, removing and annotating sketches as graph nodes.

### Lifecycle

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-LIF-001` | Create 2D sketch | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `sketch.create`; `test_plate_end_to_end` |
| `SK-LIF-002` | Exit sketch after normal creation | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` |
| `SK-LIF-003` | Edit an existing sketch | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Spec §9; no update op |
| `SK-LIF-004` | Delete a sketch | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Graph deletion (5.2); no op |
| `SK-LIF-005` | Multiple sketches per part | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Base plus hole sketches; `test_plate_end_to_end` |
| `SK-LIF-006` | Face sketch lists its host extrude as a dependency | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_the_sketch_must_list_the_extrude_as_a_dependency` |
| `SK-LIF-007` | Sketch visibility (show / hide) | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-LIF-008` | 3D sketch (create) | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 (5.3.4) |
| `SK-LIF-009` | Sketch block | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-LIF-010` | Leave sketch mode when creation fails | In Scope | P1 | Implemented | N/A | N/A | ✅ | ⬜ | ⬜ | ⬜ | `finally` in `SketchAdapter`; no test fails mid-sketch |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md); [spec §9](../../../docs/architecture/incremental-sync.md) |
| Compiler | [lower.py](../../../packages/cad-compiler/src/cad_compiler/lowering/lower.py) |
| Adapter | [SketchAdapter.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs) |
| Tests | [test_live_part_chain.py](../../../tests/live/test_live_part_chain.py), [test_live_part_ops.py](../../../tests/live/test_live_part_ops.py) |
| Depends on | [`SK-PLN`](#sk-pln--sketch-placement-and-coordinate-frames) |

**Notes and limitations**

- `sketch.create` opens, populates and closes the sketch in one operation; no separate edit state is exposed.
- Node options such as `display_name` and `suppressed` are tracked once, in [`CM-NOD`](../part-features/common-and-document.md#cm-nod--graph-node-options).
