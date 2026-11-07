# Sketch Entities

Geometry primitives.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SK-ENT — Sketch Entities

Geometry primitives allowed in a sketch. Schema: [v0.json](../../../schemas/part-feature-graph/v0.json).

### Lines

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-ENT-001` | Line (start, end) | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Plate outline; `test_plate_end_to_end` |
| `SK-ENT-002` | Construction flag (`construction: true`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.4 `construction`; not in schema |
| `SK-ENT-003` | Centerline (construction line) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `CreateCenterLine` ◐ |

### Rectangles and polygons

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-ENT-004` | Rectangle expressed as four `line` entities | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Authoring recipe; `test_plate_end_to_end` |
| `SK-ENT-005` | Corner `rectangle` entity | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.4: stored as lines plus group |
| `SK-ENT-006` | Center `rectangle` entity | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SK-ENT-007` | Three-point corner rectangle | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-008` | Three-point center rectangle | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-009` | Parallelogram | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-010` | Polygon (regular, N sides) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |

### Circles and arcs

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-ENT-011` | Circle (center, diameter) | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end`; its use as a profile is tracked in [`CF-EXT`](../part-features/cut-features.md#cf-ext--extruded-cut) and [`BF-EXT`](../part-features/base-features.md#bf-ext--extruded-bossbase) |
| `SK-ENT-012` | Perimeter (three-point) circle | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-013` | Center-point arc | In Scope | P1 | Tested | ✅ | ✅ | ✅ | ⬜ | ✅ | ⬜ | 5.3.2 Tier 1; `test_expected_geometry_with_arcs`; `CreateArc` ◐ |
| `SK-ENT-014` | Three-point arc | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SK-ENT-015` | Tangent arc | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SK-ENT-016` | Arc direction (`ccw` / `cw`) | In Scope | P1 | Tested | ✅ | ✅ | ✅ | ⬜ | ✅ | ⬜ | `test_expected_geometry_with_arcs`; `CreateArc` direction ±1 ◐ |

### Curves and other

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-ENT-017` | Ellipse | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `SK-ENT-018` | Partial ellipse | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-019` | Spline (fit points) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 |
| `SK-ENT-020` | Style spline | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-021` | Straight slot | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.2 Tier 1 |
| `SK-ENT-022` | Centerpoint straight slot | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-023` | Arc slot | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-024` | Centerpoint arc slot | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `SK-ENT-025` | Sketch point | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `CreatePoint` ◐ |
| `SK-ENT-026` | Sketch text | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1; Create undecided |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.4](../../../docs/specifications/ir-specification.md#224-sketch-model) §22.4.1; [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.4 |
| SOLIDWORKS API | `CreateLine`, `CreateCircleByRadius` ✔; `CreateArc`, `CreateCenterLine`, `CreatePoint` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); other creation calls unverified |
| IR / schema | [sketch.json](../../../schemas/part-feature-graph/features/sketch.json), [v0.json](../../../schemas/part-feature-graph/v0.json), [model.py](../../../packages/cad-ir/src/cad_ir/part_feature_graph/model.py) |
| Compiler | [lower.py](../../../packages/cad-compiler/src/cad_compiler/lowering/lower.py), [semantic.py](../../../packages/cad-compiler/src/cad_compiler/validator/semantic.py) |
| Adapter | [SketchAdapter.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs) |
| Tests | [test_live_part_chain.py](../../../tests/live/test_live_part_chain.py), [test_live_part_ops.py](../../../tests/live/test_live_part_ops.py), [test_rules.py](../../../packages/cad-compiler/tests/test_rules.py), [test_part_feature_graph.py](../../../packages/cad-ir/tests/test_part_feature_graph.py) |
| Depends on | [`SK-PLN`](sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames) |

**Notes and limitations**

- Rectangle exists only as an authoring recipe of four `line` entities; no `rectangle` entity is in the schema.
- Circles are stored by diameter (22.4.1); the adapter converts to a radius.
- Spec §5.3.1: the IR carries final geometry, not editing steps.
