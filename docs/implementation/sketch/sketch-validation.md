# Sketch Validation

Input checks and constraint-state checks.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SK-VAL — Sketch Validation

Checks on sketch input and on the built sketch. Pure validator rules need no SOLIDWORKS, so their Adapter and Execution layers are N/A.

### Contours and geometry

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-VAL-001` | Sketch has at least one entity | In Scope | P0 | Implemented | ✅ | N/A | N/A | N/A | ✅ | N/A | Schema `minProperties`; the parser refuses it, but no test covers it |
| `SK-VAL-002` | Closed contour: lines chain into one loop | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_single_line_loop_accepted` |
| `SK-VAL-003` | Open contour rejected | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `_make_open_loop` in `test_rules` |
| `SK-VAL-004` | Unordered line segments accepted and chained | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_unordered_sketch_lines` |
| `SK-VAL-005` | Self-intersecting loop rejected | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `_make_self_intersecting` in `test_rules` |
| `SK-VAL-006` | Several separate line loops rejected | In Scope | P1 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_separate_line_loops_rejected` |
| `SK-VAL-007` | Zero-length line rejected | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_degenerate_rejected` |
| `SK-VAL-008` | Circle diameter below 0.01 mm rejected | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_degenerate_rejected` |
| `SK-VAL-009` | Lines and circles mixed in one extrude profile rejected | In Scope | P1 | Implemented | ✅ | ✅ | N/A | N/A | ✅ | N/A | `_check_extrude_profile`; `test_cut_mixing_lines_and_circles_rejected` covers cuts only |
| `SK-VAL-010` | Nested contours (outer loop with inner holes) in one profile | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec; 22.4.6 requires one loop |
| `SK-VAL-011` | Duplicate or coincident entities | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | No spec statement |
| `SK-VAL-012` | Plane is a standard plane or an extrude cap face | In Scope | P0 | Tested | ✅ | ✅ | N/A | N/A | ✅ | N/A | `test_unsupported_plane`, `test_only_the_cap_faces_are_supported` |

### Constraint state and consistency

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-VAL-013` | Relations and dimensions refer to existing entities | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.6 |
| `SK-VAL-014` | Entity, relation and dimension IDs do not collide | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.6 |
| `SK-VAL-015` | Seed consistency (coordinates satisfy constraints) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.4 |
| `SK-VAL-016` | Degrees-of-freedom estimate (advisory) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.5 |
| `SK-VAL-017` | Under-, fully-defined state read from SOLIDWORKS | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | `ISketch.GetConstrainedStatus` ◐ |
| `SK-VAL-018` | Over-defined or conflicting constraints detected | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.5 `over_defined` (conflicting constraints) |
| `SK-VAL-019` | `expected_state` field (`any`, `fully_defined`) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.5 |
| `SK-VAL-020` | Solver failure (`no_solution`, `invalid_solution`) fails the contract | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.5 |
| `SK-VAL-021` | `unknown` state gives `not_evaluated` | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.4.5 |

### Built-sketch checks

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-VAL-022` | Sketch entity count postcondition | In Scope | P1 | Verified | N/A | ✅ | ✅ | ✅ | ✅ | ✅ | Required contract check in every job (`contracts.py`, `plan_job.py`); `test_plate_end_to_end` commits only if it passes |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.4](../../../docs/specifications/ir-specification.md#224-sketch-model) §22.4.5–22.4.6 |
| Compiler | [semantic.py](../../../packages/cad-compiler/src/cad_compiler/validator/semantic.py) |
| IR / schema | [sketch.json](../../../schemas/part-feature-graph/features/sketch.json) |
| Tests | [test_rules.py](../../../packages/cad-compiler/tests/test_rules.py), [test_part.py](../../../packages/cad-verification/tests/test_part.py) |
| Depends on | `SK-ENT` |

**Notes and limitations**

- Tested means passing unit tests. These rules refuse input before SOLIDWORKS runs, so no live test applies.
- Rules about cuts are in `CF-EXT`; selected contours are in `BF-EXT` and `CF-EXT`; post-build checks are in `CM-VER`.
