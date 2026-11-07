# Common Options and Document

Cross-cutting rows: part document, node options, verification, parameters, editing.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## CM-DOC — Part Document

Creating and saving the part document that holds the graph.

### Document

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CM-DOC-001` | Create part from template | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` |
| `CM-DOC-002` | Save as `.SLDPRT` at the target path | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` |
| `CM-DOC-003` | Refuse to overwrite an existing file | In Scope | P0 | Implemented | N/A | ✅ | ✅ | ✅ | ✅ | ⬜ | `test_part_create_refuses_existing_file` exists; no recorded run of `test_live_part_ops` |
| `CM-DOC-004` | Template with reordered planes refused | In Scope | P0 | Implemented | N/A | ✅ | ✅ | ✅ | ✅ | ⬜ | `test_template_with_reordered_planes` asserts refusal but can skip, and the live run record has one unnamed skip |
| `CM-DOC-005` | Template with an extra feature refused | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_template_with_extra_feature` (job fails feature verification) |
| `CM-DOC-006` | Non-ASCII target path | In Scope | P1 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_non_ascii_path` |
| `CM-DOC-007` | Set material | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1 `SetMaterial` |
| `CM-DOC-008` | Set custom properties | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1 `SetCustomProperties` |
| `CM-DOC-009` | Open dirty document untouched by a job | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_open_dirty_document_untouched` |
| `CM-DOC-010` | Source-file custody across the pipeline | In Scope | P0 | Partially Implemented | N/A | ◐ | ⬜ | ⬜ | ⬜ | ⬜ | ADR-022; `AUTH_SOURCE_WRITE_NOT_ALLOWED` in `plan_job.py` and `PartCreationAdapter`; whole-policy coverage not audited |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2 |
| SOLIDWORKS API | `ISldWorks.NewDocument`, `IModelDoc2.SaveAs4` ✔ |
| Adapter | [PartCreationAdapter.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/PartCreationAdapter.cs) |
| Compiler | [lower.py](../../../packages/cad-compiler/src/cad_compiler/lowering/lower.py) |
| Tests | [test_live_part_chain.py](../../../tests/live/test_live_part_chain.py), [test_live_part_ops.py](../../../tests/live/test_live_part_ops.py) |
| Depends on | — |

## CM-NOD — Graph Node Options

Fields and rules common to every feature node.

### Identity and order

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CM-NOD-001` | Node IDs match the naming pattern | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `ItemId` cases in `test_schema_fixtures.py` |
| `CM-NOD-002` | Explicit `dependencies` | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_the_sketch_must_list_the_extrude_as_a_dependency` |
| `CM-NOD-003` | Implied `profile` dependency | In Scope | P0 | Implemented | ✅ | ✅ | N/A | N/A | ✅ | N/A | `resolve_dependencies`; no dedicated test |
| `CM-NOD-004` | Deterministic topological build order | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_build_order_plate` |
| `CM-NOD-005` | Cycle rejection | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `IR_CYCLE`; `test_cycle_rejected` |
| `CM-NOD-006` | Unsupported feature type refused, never approximated | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `refuse_*` cases in `test_part_ir_benchmark.py`; `test_only_the_cap_faces_are_supported` |

### Optional fields

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CM-NOD-007` | `display_name` | In Scope | P2 | Partially Implemented | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | In IR and schema; not applied in SOLIDWORKS; K31 |
| `CM-NOD-008` | `realizes` (functional feature names) | In Scope | P2 | Partially Implemented | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | In IR and schema; not consumed; K31 |
| `CM-NOD-009` | `suppressed` | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.1, K31; absent from schema |
| `CM-NOD-010` | `x_solidworks` extension object | In Scope | P3 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.1 |
| `CM-NOD-011` | `parameters` for non-shared parameters | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.1 |
| `CM-NOD-012` | `ParamRef` with more than two segments | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | K23 |
| `CM-NOD-013` | Compiler defaults table (`defaults/<version>.json`) | In Scope | P1 | Partially Implemented | ⬜ | ◐ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.6; file exists with empty tables, nothing loads it, and `plan_job.py` passes `defaults={}` |
| `CM-NOD-014` | Roles (`<node>.<role>`) beyond cap faces | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.7.5, K23 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.7](../../../docs/architecture/feature-schema-guide.md) §5.7.1–5.7.6 |
| SOLIDWORKS API | — |
| IR / schema | [v0.json](../../../schemas/part-feature-graph/v0.json), [model.py](../../../packages/cad-ir/src/cad_ir/part_feature_graph/model.py) |
| Compiler | [lower.py](../../../packages/cad-compiler/src/cad_compiler/lowering/lower.py), [semantic.py](../../../packages/cad-compiler/src/cad_compiler/validator/semantic.py) |
| Tests | [test_part_feature_graph.py](../../../packages/cad-ir/tests/test_part_feature_graph.py), [test_rules.py](../../../packages/cad-compiler/tests/test_rules.py) |
| Depends on | — |

## CM-VER — Result Verification

Checks applied after a build; owned here once and applied to every feature.

### Checks

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CM-VER-001` | Rebuild health | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-002` | Solid body count | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-003` | Feature tree matches the graph | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-004` | Bounding box | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-005` | Volume | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-006` | Surface area | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-007` | Center of mass | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-008` | Cylindrical faces (holes) | In Scope | P0 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | `test_plate_end_to_end` asserts every check on the reopened part |
| `CM-VER-009` | Absent measurement is `not_evaluated`, never passed | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_empty_measurement_passes_nothing` |
| `CM-VER-010` | Expected geometry for fillets, sweeps and other non-closed-form features | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | K16 |
| `CM-VER-011` | Face and edge level checks | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | K28 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.5](../../../docs/specifications/ir-specification.md#225-feature-model); [ADR-063](../../../docs/adr/ADR-063-observation-verification-boundary.md) |
| SOLIDWORKS API | `IMassProperty`, `IFace2`, rebuild status ✔ |
| Adapter | [PartMeasureAdapter.cs](../../../apps/execution-server/ExecutionServer.Adapters/Parts/PartMeasureAdapter.cs) |
| Verification | [part.py](../../../packages/cad-verification/src/cad_verification/part.py) |
| Tests | [test_part.py](../../../packages/cad-verification/tests/test_part.py), [test_live_part_chain.py](../../../tests/live/test_live_part_chain.py) |
| Depends on | — |

## CM-EQN — Parameters and Equations

Named parameters, equations and global variables. The one authoritative entry; sketch and feature rows link here.

### Parameters

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CM-EQN-001` | Global variables | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 2 |
| `CM-EQN-002` | Equations driving dimensions or fields | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 2 |
| `CM-EQN-003` | Linked dimensions | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `CM-EQN-004` | Dimensional unit check of expressions | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.8.3 Proposed |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.3; [ADR-065](../../../docs/adr/ADR-065-part-parameters-and-expressions.md) (Proposed) |
| SOLIDWORKS API | `IEquationMgr` ? |
| Tests | — |
| Depends on | — |

## CM-LIF — Editing and Configuration

Changing a built part and configurations.

### Editing

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CM-LIF-001` | Update a feature parameter | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Spec §9 |
| `CM-LIF-002` | Delete a feature | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.2 |
| `CM-LIF-003` | Graph diff and incremental sync | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.2; spec §9 |
| `CM-LIF-004` | Feature reorder and rollback | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Phase 4 |

### Configurations

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CM-LIF-005` | Configurations (create) | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 |
| `CM-LIF-006` | Design tables | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [spec §9](../../../docs/architecture/incremental-sync.md); [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.4 |
| SOLIDWORKS API | `ModifyDefinition` ◐ |
| Tests | — |
| Depends on | — |
