# Sketch Dimensions

Driving dimensions.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## SK-DIM — Sketch Dimensions

Driving dimensional constraints. None are in the schema yet.

### Dimension types

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-DIM-001` | Linear (distance) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | type `distance` |
| `SK-DIM-002` | Horizontal distance | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | type `horizontal` |
| `SK-DIM-003` | Vertical distance | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | type `vertical` |
| `SK-DIM-004` | Angular | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | type `angle` |
| `SK-DIM-005` | Radius | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | type `radius` |
| `SK-DIM-006` | Diameter | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | type `diameter` |
| `SK-DIM-007` | Arc length | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.4.3 |

### Behaviour

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SK-DIM-008` | Driving dimension addressable as `<sketch>.<dim>` | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ParamRef; nesting gap K23 |
| `SK-DIM-009` | Driven (reference) dimension | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Spec: every dimension is driving |
| `SK-DIM-010` | Modify a dimension value on an existing sketch | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Spec §9; read-back caveat |
| `SK-DIM-011` | Dimension text placement (derived, no meaning) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | K27 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.4](../../../docs/specifications/ir-specification.md#224-sketch-model) §22.4.3 |
| SOLIDWORKS API | `IModelDocExtension.AddDimension`, `IModelDoc2.AddDimension2`, `IDimension.SetSystemValue3` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); multi-step with text placement (K27) |
| Tests | — |
| Depends on | `SK-ENT` |

**Notes and limitations**

- A circle's diameter is a stored entity parameter, not a driving dimension (tracked in `SK-ENT`).
- Equations and linked dimensions are Tier 2 and tracked once, in `CM-EQN`.
