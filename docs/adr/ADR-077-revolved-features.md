# ADR-077: Revolved Boss/Base and Revolved Cut Semantics

- **Status:** Accepted
- **Date:** 2026-11-07
- **Deciders:** Architecture Team, CAD Core Team
- **Consulted:** Guideline G1, Guideline G2, ADR-010, ADR-035, ADR-059, ADR-068, ADR-070, ADR-076
- **Informed:** Core Service, Execution Server, Verification Engine

---

## Context and Problem Statement

Adding material or cutting material by revolving a planar 2D profile around an axis of rotation is one of the foundational 3D modeling operations in mechanical CAD (spec §22.5.2, roadmap A5). It is tracked in implementation checklists as `BF-REV-001` through `BF-REV-016` (Revolved Boss/Base) and `CF-REV-001` through `CF-REV-006` (Revolved Cut), alongside sketch construction line support (`SK-ENT-002`, `SK-ENT-003`).

We need a clean-room (ADR-010), deterministic, CAD-neutral representation in Part Feature Graph IR that compiles to IPC operations and maps reliably to the SOLIDWORKS COM API (`IFeatureManager.FeatureRevolve2`) without using banned APIs such as `SelectByID2` (ADR-059, spec §8.3 rule 11).

---

## Decision Drivers

1. **IR Neutrality & Type Separation (§22.5.2):** `revolve` and `cut_revolve` must be separate IR feature types because their contracts differ (`revolve` adds volume, `cut_revolve` removes volume from an existing solid body), even though SOLIDWORKS routes both through `FeatureRevolve2` with `IsCut`.
2. **Axis Representation:** An axis of revolution can be:
   - A centerline (construction line) within the profile sketch (`axis: "sketch_id.cl"` or auto-detected if the sketch contains a single centerline).
   - A reference coordinate axis (`axis:x`, `axis:y`, `axis:z` or `plane:front`, `plane:top`, `plane:right` normal).
   - An existing model axis (cylindrical face or circular edge from a prior feature).
3. **Sketch Construction Geometry:** Sketches must support construction lines (`Line(construction=True)` / `CreateCenterLine`), enabling axis definition directly within the profile sketch (`SK-ENT-002`, `SK-ENT-003`).
4. **Angular Units & Direction:** IR specifies `angle` in degrees in $(0, 360]$. The compiler lowers this to radians for the C# adapter. Symmetrical revolutions use `mid_plane: true`, mapping to `swEndCondMidPlane`.
5. **Selection Marks for COM API:** In accordance with SOLIDWORKS API requirements:
   - Mark 0: Profile sketch (`IFeature.Select2(false, 0)`).
   - Mark 4: Revolution axis (`ISketchSegment.Select2(true, 4)` or `IEntity.Select4(true, selData)` with `selData.Mark = 4`).
6. **Closed-Form Verification:** Expected volume is computed using Pappus's Centroid Theorem ($V = \theta A \bar{r}$). Revolution faces parallel to the axis are verified as `ExpectedCylinder`.
7. **Native Feature Type Identification:** SOLIDWORKS names revolved features `"Revolution"` (for boss/base) and `"RevCut"` (for cuts).

---

## Considered Alternatives

- **Alternative 1: Single polymorphic `revolve` node with `is_cut` boolean:** Rejected. Violates spec §22.5.2 ("A cut is not a boss with a flag"). Separate types enforce distinct preconditions in the semantic validator (e.g. cut requires prior body).
- **Alternative 2: Rely exclusively on 3D coordinate axes:** Rejected. In mechanical design, the axis of revolution is most naturally defined in the profile sketch as a centerline.
- **Alternative 3: `SelectByID2("Line1@Sketch1", "EXTSKETCHSEGMENT", ...)`:** Rejected. Spec §8.3 and ADR-059 strictly ban `SelectByID2`. Selection must use object references obtained through `IFeature` and `ISketch.GetSketchSegments()`.

---

## Decision Outcome

1. **IR Schema:**
   - Define `revolve` node schema with required `profile` (SketchRef), optional `axis` (AxisRef, defaults to sketch centerline if omitted), `angle` (number > 0 and <= 360, default 360), optional `mid_plane` (boolean, default false), `reverse` (boolean, default false), `thin` (Thin object), and `merge_result` (boolean, default true).
   - Define `cut_revolve` node schema with same geometry inputs, requiring prior solid feature in dependencies.
   - Add optional `construction: boolean = false` to `Line` sketch entity.
2. **Compiler Lowering:**
   - Lowers `revolve` and `cut_revolve` to `feature.create` with `type: "revolve"` or `"cut_revolve"`, passing `axis`, `angle`, `mid_plane`, `reverse`, `merge`.
   - Lowers lines with `construction: true` to `sketch.create` entity with `construction: true`.
3. **C# Adapter Implementation:**
   - In `SketchAdapter.cs`, when `entity.Construction == true`, call `sm.CreateCenterLine(x0, y0, 0, x1, y1, 0)`.
   - In `FeatureAdapter.cs`, select sketch with Mark 0. For axis:
     - If `p.Axis` points to a sketch segment or is omitted, find the construction line in the profile sketch and call `sketchSegment.Select2(true, 4)`.
     - If `p.Axis` is a coordinate axis (`axis:x`, `axis:y`, etc.) or existing cylinder, select with Mark 4 via `SelectData`.
   - Invoke `doc.FeatureManager.FeatureRevolve2(...)`:
     - `SingleDir`: `!(p.MidPlane ?? false)`
     - `IsSolid`: `true`
     - `IsThin`: `false`
     - `IsCut`: `p.Type == FeatureCreateParamsType.CutRevolve`
     - `ReverseDir`: `p.Reverse ?? false`
     - `Dir1Type`: `(p.MidPlane ?? false) ? (int)swEndConditions_e.swEndCondMidPlane : (int)swEndConditions_e.swEndCondBlind`
     - `Dir1Angle`: `p.Angle * Math.PI / 180.0`
     - `Merge`: `p.Merge ?? true`
     - `UseFeatScope`: `false`
     - `UseAutoSelect`: `true`
   - Release all temporary COM objects (`ISketch`, `ISketchSegment`, enumerators) via `ComScope`.
4. **Verification Engine:**
   - Apply Pappus's Centroid Theorem $V = \theta A \bar{r}$ to calculate nominal volume for closed cross-sections.
   - For $360^\circ$ full revolutions, verify expected cylinder at outer and inner radii.
   - Map native feature types to `"Revolution"` and `"RevCut"`.

---

## Consequences

- **Positive:**
  - Enables rotational parts (cylinders, shafts, bushings, flanges, stepped spindles) and rotational cuts (grooves, O-ring recesses, counterbores).
  - Preserves clean-room purity and COM lifecycle discipline (0 leaks, 0 banned APIs).
  - Provides rigorous closed-form verification for rotational geometry.
- **Negative / Risks:**
  - Complex self-intersecting 2D profiles can fail in the CAD kernel; semantic validation must verify profiles are well-formed and non-overlapping.
