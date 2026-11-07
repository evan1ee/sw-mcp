# Reference Geometry

Planes, axes, points, coordinate systems and curves.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## RG-PLN — Reference Plane

Datum plane. IR node `plane`.

### Created planes

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `RG-PLN-001` | Offset from plane or face | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `offset` |
| `RG-PLN-002` | Angle to plane or face | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `angle` |
| `RG-PLN-003` | Through entities (three points, line and point) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `through` |
| `RG-PLN-004` | Parallel at point | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-PLN-005` | Perpendicular to curve | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-PLN-006` | Mid plane | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-PLN-007` | Tangent to face | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-PLN-008` | Plane on surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-PLN-009` | Flip / reverse normal | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2; [22.3.4](../../../docs/specifications/ir-specification.md#2234-reference-geometry-nodes) |
| SOLIDWORKS API | `IFeatureManager.InsertRefPlane` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); returns an untyped object |
| Tests | — |
| Depends on | — |

**Notes and limitations**

- Standard planes are not created features; they are tracked once, in [`SK-PLN`](../sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames).

## RG-AXS — Reference Axis

Datum axis. IR node `axis`.

### Definition types

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `RG-AXS-001` | From line or edge | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.3.4 |
| `RG-AXS-002` | Intersection of two planes | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `two_planes` |
| `RG-AXS-003` | Through two points | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `two_points` |
| `RG-AXS-004` | From a cylindrical face | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `cylinder` |
| `RG-AXS-005` | Through a point normal to a surface | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.3.4 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.3.4](../../../docs/specifications/ir-specification.md#2234-reference-geometry-nodes) |
| SOLIDWORKS API | `IModelDoc2.InsertAxis2` ◐ ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); returns a boolean only |
| Tests | — |
| Depends on | — |

## RG-PNT — Reference Point

Datum point. IR node `point`.

### Definition types

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `RG-PNT-001` | Explicit position (`position`) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4; the only form the spec defines |
| `RG-PNT-002` | At vertex or arc center | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.3.4 |
| `RG-PNT-003` | Center of face | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.3.4 |
| `RG-PNT-004` | Intersection of entities | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.3.4 |
| `RG-PNT-005` | Projection onto a surface | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not in 22.3.4 |
| `RG-PNT-006` | Along a curve (distance, percentage, evenly) | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.3.4](../../../docs/specifications/ir-specification.md#2234-reference-geometry-nodes) |
| SOLIDWORKS API | `IFeatureManager.InsertReferencePoint` (4 params) ◐ |
| Tests | — |
| Depends on | — |

## RG-CSY — Reference Coordinate System

Datum coordinate system. IR node `coordinate_system`.

### Definition

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `RG-CSY-001` | Origin point | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `origin` |
| `RG-CSY-002` | X and Y axis direction references | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 22.3.4 `x_axis`, `y_axis` |
| `RG-CSY-003` | Flip axes | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [22.3.4](../../../docs/specifications/ir-specification.md#2234-reference-geometry-nodes) |
| SOLIDWORKS API | `IFeatureManager.InsertCoordinateSystem` ? ([8.9.11](../../../docs/specifications/solidworks-adapter.md#8911-api-capability-mapping)); remarks unread |
| Tests | — |
| Depends on | — |

## RG-CRV — Reference Curves

Curve features used as paths, drivers and parting lines.

### Curves

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `RG-CRV-001` | Helix (create) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3; spring benchmark |
| `RG-CRV-002` | Helix: height and revolution | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-CRV-003` | Helix: pitch and revolution | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-CRV-004` | Helix: spiral and variable pitch | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-CRV-005` | Helix: taper, start angle, direction | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-CRV-006` | Equation-driven curve (gear involute) | In Scope | P2 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3.3 Tier 2 `EquationCurve`; gear benchmark |
| `RG-CRV-007` | Split line (parting line) | In Scope | P1 | Specified | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 1; molded housing |
| `RG-CRV-008` | Split line: projection, silhouette, intersection types | Under Evaluation | P2 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-CRV-009` | Composite curve | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-CRV-010` | Projected curve | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |
| `RG-CRV-011` | Curve through XYZ or reference points | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Not named in the spec |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2–5.3.3 |
| SOLIDWORKS API | `IModelDoc2.InsertHelix` (10 params), `InsertSplitLineProject` (2), `InsertSplitLineSil` (0), `InsertCompositeCurve` (0); `IFeatureManager.InsertVariablePitchHelix` (4), `InsertSplitLineIntersect` (1); `ISketchManager.CreateEquationSpline2` (11) ◐ |
| Tests | — |
| Depends on | [`SK-ENT`](../sketch/sketch-entities.md#sk-ent--sketch-entities) |
